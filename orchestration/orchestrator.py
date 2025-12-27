import json
from typing import Dict, List, Optional
from datetime import datetime
import openai

from config.settings import settings
from observability.logger import logger
from observability.metrics import QueryMetrics, metrics_collector
from orchestration.prompts import SYSTEM_PROMPT, create_user_prompt
from orchestration.tools import TOOLS, execute_search_codebase
from retrieval.retriever import HybridRetriever
from guardrails.validator import ResponseValidator, InputValidator

class LLMOrchestrator:
    """Orchestrates LLM calls with tool usage, retrieval, and guardrails"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.llm.api_key)
        self.model = settings.llm.model
        self.temperature = settings.llm.temperature
        self.max_tokens = settings.llm.max_tokens
        self.retriever = HybridRetriever()
        self.response_validator = ResponseValidator()
        self.input_validator = InputValidator()
    
    def query(
        self,
        user_query: str,
        repo_name: Optional[str] = None,
        top_k: int = 5
    ) -> Dict:
        """
        Process user query with LLM, retrieval, and guardrails
        
        Args:
            user_query: User's question
            repo_name: Optional repository filter
            top_k: Number of context chunks to retrieve
        
        Returns:
            Dict with response, citations, validation, and metrics
        """
        start_time = datetime.utcnow()
        
        # Validate input
        is_valid, error_msg = self.input_validator.validate_query(user_query)
        if not is_valid:
            return {
                "response": f"Invalid query: {error_msg}",
                "citations": [],
                "validation": {
                    "is_valid": False,
                    "errors": [error_msg],
                    "warnings": []
                },
                "metrics": {}
            }
        
        with logger.operation("llm_query", query=user_query[:100]):
            try:
                # Retrieve relevant context
                context_chunks = self.retriever.retrieve(
                    query=user_query,
                    top_k=top_k,
                    repo_name=repo_name
                )
                
                logger.info("Retrieved context", chunks=len(context_chunks))
                
                if not context_chunks:
                    return {
                        "response": "I couldn't find any relevant documentation for your question. Try rephrasing or check if the repository has been indexed.",
                        "citations": [],
                        "validation": {
                            "is_valid": True,
                            "errors": [],
                            "warnings": ["No relevant context found"]
                        },
                        "metrics": {}
                    }
                
                # Create prompt with context
                user_prompt = create_user_prompt(user_query, context_chunks)
                
                # Call LLM
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    tools=TOOLS,
                    tool_choice="auto"
                )
                
                message = response.choices[0].message
                
                if message.tool_calls:
                    response_text = self._handle_tool_calls(
                        message.tool_calls,
                        user_query,
                        context_chunks
                    )
                else:
                    response_text = message.content
                
                # Validate response
                is_valid, errors, warnings = self.response_validator.validate(
                    response_text,
                    context_chunks
                )
                
                # Add warnings to response if any
                if warnings:
                    response_text = self.response_validator.add_warnings_to_response(
                        response_text,
                        warnings
                    )
                
                # Extract citations
                citations = self._extract_citations(response_text, context_chunks)
                
                # Calculate cost
                tokens_used = response.usage.total_tokens
                cost = self._estimate_cost(tokens_used)
                
                # Record metrics
                metrics = QueryMetrics(
                    query=user_query,
                    start_time=start_time,
                    end_time=datetime.utcnow(),
                    chunks_retrieved=len(context_chunks),
                    llm_model=self.model,
                    tokens_used=tokens_used,
                    cost_usd=cost,
                    citations=citations
                )
                metrics_collector.record_query(metrics)
                
                logger.info(
                    "Query completed",
                    query=user_query[:100],
                    tokens=tokens_used,
                    cost_usd=round(cost, 4),
                    citations_count=len(citations),
                    validation_passed=is_valid
                )
                
                return {
                    "response": response_text,
                    "citations": citations,
                    "context_chunks": context_chunks,  # For debugging
                    "validation": {
                        "is_valid": is_valid,
                        "errors": errors,
                        "warnings": warnings
                    },
                    "metrics": metrics.to_dict()
                }
                
            except Exception as e:
                logger.error("Query failed", query=user_query[:100], error=str(e))
                raise
    
    def _handle_tool_calls(
        self,
        tool_calls,
        original_query: str,
        context_chunks: List[Dict]
    ) -> str:
        """Handle tool calls from LLM"""
        
        logger.info("LLM requested tool calls", count=len(tool_calls))
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            logger.info(
                "Executing tool",
                tool=function_name,
                arguments=arguments
            )
            
            if function_name == "search_codebase":
                # Re-retrieve with different parameters based on tool call
                additional_results = self.retriever.retrieve(
                    query=arguments.get('query', original_query),
                    top_k=3,
                    file_type=arguments.get('file_type', 'any')
                )
                
                # For now, just acknowledge the tool was used
                # In production, you'd make another LLM call with tool results
                return (
                    f"I searched the codebase and found relevant information. "
                    f"(Tool calling executed successfully)"
                )
        
        return "Tool execution completed"
    
    def _extract_citations(self, response_text: str, context_chunks: List[Dict]) -> List[str]:
        """Extract file paths mentioned in response"""
        citations = []
        
        for chunk in context_chunks:
            file_path = chunk.get('file_path', '')
            if file_path and file_path in response_text:
                citations.append(file_path)
        
        return list(set(citations))
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate API cost"""
        input_cost_per_1k = 0.0025
        output_cost_per_1k = 0.01
        
        input_tokens = int(tokens * 0.6)
        output_tokens = int(tokens * 0.4)
        
        cost = (
            (input_tokens / 1000) * input_cost_per_1k +
            (output_tokens / 1000) * output_cost_per_1k
        )
        
        return cost