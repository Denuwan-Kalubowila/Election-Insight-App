from utils.utils import get_embeddings, get_retriever, get_llm
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph, START
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from typing import TypedDict, Literal, List
from pydantic import BaseModel, Field

response:str

class FactChecker(TypedDict):
    claim: str
    party: str
    score: str
    verdict: str
    documents: List[str]
    
class RouteQuery(BaseModel):
    data_source: Literal["vectorstore", "web_search"] = Field(
        ...,
        description="Given a user question choose to route it to web search or a vectorstore.",)

def fact_retrieve_node(fact:FactChecker):
    question=f'''{fact['claim']}, {fact['party']}.'''
    
    retrieve_documents=get_retriever().invoke(question)
    
    return {"documents": retrieve_documents}

def fact_generate_node(fact:FactChecker):
    percentage_prompt_template=  """You are a supporter who has access to the full manifesto of all candidates in the upcoming election.
        Decide on the facts presented : {FACTS}. Provide accurate, fact-based responses using policy statements, and offer comparisons if asked.
        Provide as a percentage how much truth there is for the final conclusion
        Using only the given context : {CONTEXT}
        Ensure that all answers are concise, neutral and based on the information provided in the policy statements.
        If the answer cannot be found in the context, please state "I don't know". Do not try to prepare an answer."""

    question_prompt=ChatPromptTemplate.from_template(percentage_prompt_template)

    question_chain = (
        {"FACTS":RunnablePassthrough(), "CONTEXT": RunnablePassthrough()}
        | question_prompt
        | get_llm()
        | StrOutputParser()
        )
    
    global percentage_response

    percentage_response=question_chain.invoke({"FACT": fact["claim"], "CONTEXT": fact["documents"]})
    
    return {'score' :percentage_response}

def fact_verdict_node(fact:FactChecker):
    verdict_prompt_template=  """You are a fact checker tasked with providing a final conclusion percentage: {SCORE} based on a specific party: {PARTY}.
    Provide a score out of 10 for each candidate or party based on the provided evidence.
    Indicate as a percentage how much truth there is in the final conclusion.final conclusion provide as english,sinhala and tamil languages.

    - If the score is less than 50%, output: "This party cheats or provides misleading information."
    - If the score is between 50% and 75%, output: "This party can contribute something positive to the country, but there are concerns."
    - If the score is greater than 75%, output: "This party's claims are almost entirely truthful."

    Score: {SCORE}
    Party: {PARTY}
    Final Conclusion:
        1. English
        2. Sinhala
        3. Tamil
    """

    verdict_prompt=ChatPromptTemplate.from_template(verdict_prompt_template)

    verdict_chain = (
        {"SCORE":RunnablePassthrough(), "PARTY": RunnablePassthrough()}
        | verdict_prompt
        | get_llm()
        | StrOutputParser()
        )
    
    global verdict_response

    verdict_response=verdict_chain.invoke({"SCORE": fact["score"], "PARTY": fact["party"]})
    
    return {'verdict' : verdict_response}

def web_search_tool(face:FactChecker):
    structured_llm_router = get_llm().with_structured_output(RouteQuery)



factFlow=StateGraph(FactChecker)
factFlow.add_node("fact_retrieve_node", fact_retrieve_node)
factFlow.add_node("fact_generate_node", fact_generate_node)
factFlow.add_node("fact_verdict_node", fact_verdict_node)

factFlow.add_edge(START, "fact_retrieve_node")
factFlow.add_edge("fact_retrieve_node", "fact_generate_node")
factFlow.add_edge("fact_generate_node", "fact_verdict_node")
factFlow.add_edge("fact_verdict_node", END)

graph=factFlow.compile()


def fact_checker(party:str, claim:str):
   for i in graph.stream({"party": party, "claim": claim}):
       pass
   global verdict_response
   global percentage_response

   return verdict_response, percentage_response   



