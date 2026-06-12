import json
from typing import TypedDict, List, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from fault_localizer.core.config import settings

# Define State
class AgentState(TypedDict):
    raw_failure_log: str
    summarized_failure: str
    commits: List[Dict[str, Any]]
    top_suspect: Dict[str, Any]

# Pydantic models for structured output
class CommitScore(BaseModel):
    probability_score: int = Field(description="Probability score from 0 to 100 indicating likelihood this commit caused the failure.")
    reasoning: str = Field(description="Brief explanation of why this score was assigned.")

class QAOpsAgent:
    def __init__(self, model_provider: str = None, model_name: str = None):
        model_provider = model_provider or settings.MODEL_PROVIDER
        model_name = model_name or settings.MODEL_NAME

        if model_provider == "google":
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                raise ValueError("GOOGLE_API_KEY is missing in configuration.")
            self.llm = ChatGoogleGenerativeAI(model=model_name, api_key=api_key, temperature=0.2)
        elif model_provider == "openai":
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY is missing in configuration.")
            self.llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0.2)
        elif model_provider == "openrouter":
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY is missing in configuration.")
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.2,
                default_headers={
                    "HTTP-Referer": "https://github.com/MurtazaJ2/QAOps",
                    "X-Title": "QAOps Agent"
                }
            )
        else:
            raise ValueError(f"Unsupported model provider: {model_provider}")
        
        # Build Graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("contextualize", self.contextualize_failure)
        workflow.add_node("analyze", self.analyze_commits)
        workflow.add_node("synthesize", self.synthesize_results)
        
        workflow.set_entry_point("contextualize")
        workflow.add_edge("contextualize", "analyze")
        workflow.add_edge("analyze", "synthesize")
        workflow.add_edge("synthesize", END)
        
        self.app = workflow.compile()

    def contextualize_failure(self, state: AgentState):
        """Summarize the raw failure log into a core semantic error statement."""
        print("-> Contextualizing Failure...")
        prompt = PromptTemplate.from_template(
            "You are an expert QA and DevOps engineer. "
            "Analyze the following raw build/test failure log and extract the core semantic error. "
            "Summarize what failed, the likely subsystem, and any key error messages or stack traces. "
            "Keep it concise and focus on actionable details that would relate to code changes.\n\n"
            "Raw Log:\n{raw_log}"
        )
        chain = prompt | self.llm
        result = chain.invoke({"raw_log": state['raw_failure_log']})
        
        return {"summarized_failure": result.content}

    def analyze_commits(self, state: AgentState):
        """Score each commit against the summarized failure."""
        print("-> Analyzing Commits...")
        summarized_failure = state['summarized_failure']
        commits = state['commits']
        
        from langchain_core.output_parsers import PydanticOutputParser
        parser = PydanticOutputParser(pydantic_object=CommitScore)
        
        prompt = PromptTemplate(
            template=(
                "You are an expert debugging assistant. A build/test has failed with the following issue:\n"
                "FAILURE CONTEXT:\n{failure_context}\n\n"
                "Analyze the following commit to determine the probability (0-100) that this specific commit introduced the failure. "
                "Look for semantic connections between the files changed/patch and the failure context. "
                "IMPORTANT: Even if the commit only contains a small configuration change, a renamed file/folder, or a structural change (like moving a directory or editing a Makefile/path), if it semantically aligns with the failure, score it HIGH (> 75). If you see the exact module name or feature mentioned in the failure log within the commit diff or message, score it VERY HIGH (> 90).\n\n"
                "YOU MUST RESPOND ONLY WITH VALID JSON. \n"
                "{format_instructions}\n\n"
                "COMMIT MESSAGE: {commit_message}\n"
                "FILES CHANGED & DIFFS: {diffs}"
            ),
            input_variables=["failure_context", "commit_message", "diffs"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self.llm | parser
        
        scored_commits = []
        for commit in commits:
            print(f"   Analyzing commit: {commit['sha'][:7]}...")
            
            # Format diffs
            diff_str = ""
            for f in commit['files']:
                diff_str += f"File: {f['filename']} (Status: {f['status']})\nPatch:\n{f['patch']}\n---\n"
                
            try:
                result = chain.invoke({
                    "failure_context": summarized_failure,
                    "commit_message": commit['message'],
                    "diffs": diff_str
                })
                commit['score'] = result.probability_score
                commit['reasoning'] = result.reasoning
            except Exception as e:
                print(f"   Error scoring commit {commit['sha']}: {e}")
                commit['score'] = 0
                commit['reasoning'] = f"Failed to analyze due to error: {e}"
                
            scored_commits.append(commit)
            
        return {"commits": scored_commits}

    def synthesize_results(self, state: AgentState):
        """Identify the top suspect commit."""
        print("-> Synthesizing Results...")
        commits = state['commits']
        
        if not commits:
            return {"top_suspect": None}
            
        # Find commit with highest score
        top_commit = max(commits, key=lambda x: x.get('score', 0))
        
        return {"top_suspect": top_commit}

    def run(self, raw_log: str, commits: List[Dict[str, Any]]):
        """Execute the LangGraph workflow."""
        inputs = {
            "raw_failure_log": raw_log,
            "summarized_failure": "",
            "commits": commits,
            "top_suspect": {}
        }
        return self.app.invoke(inputs)
