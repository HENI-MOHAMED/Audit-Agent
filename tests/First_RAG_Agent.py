from typing import TypedDict, Sequence, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from operator import add as add_message
from langgraph.graph import StateGraph, START, END
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
from g4f.integration.langchain import ChatAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import os 
from langgraph.prebuilt import ToolNode
import glob
from bs4 import BeautifulSoup
from langchain_deepseek import ChatDeepSeek
import requests
os.environ["OPENAI_API_KEY"] = "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"
os.environ["DEEPSEEK_API_KEY"] = "sk-c1604ea114b24b039cb20ddd50982f6b"
helper_llm = ChatDeepSeek(model="deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"), base_url='https://api.deepseek.com')
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"), base_url='https://api.openai.com/v1')
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_message]

def CreateDataBase(pdf_path: str, persist_directory: str = "./chroma_db") -> str:
    """ Creating the database from the PDF file if the Database is not already created."""
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    db = Chroma.from_documents(
        texts, 
        collection_name="pdf_data", 
        embedding=embeddings,
        persist_directory=persist_directory
    )
    return f"Database created successfully at: {persist_directory}"

def LoadDataBase(persist_directory: str = "./chroma_db", collection_name: str = "audit_documents_better_embeddings"):
    """Load the existing database from the persist directory."""
    db = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory
    )
    return db

def CreateDatabaseFromPDFLib(pdf_folder: str = "./PDF_lib", persist_directory: str = "./chroma_db_multilingual") -> str:
    """
    Creating the database from all PDF files in the PDF_lib folder using paraphrase-multilingual-mpnet-base-v2 model.
    
    Args:
        pdf_folder: Path to the folder containing PDF files (default: "./PDF_lib")
        persist_directory: Path where the Chroma database will be stored (default: "./chroma_db_multilingual")
    
    Returns:
        str: Success message with database location and number of processed PDFs
    """
    
    # Get all PDF files from the folder
    pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
    
    if not pdf_files:
        return f"No PDF files found in {pdf_folder}"
    
    all_texts = []
    
    # Process each PDF file
    for pdf_path in pdf_files:
        try:
            print(f"Processing: {os.path.basename(pdf_path)}")
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            texts = text_splitter.split_documents(documents)
            all_texts.extend(texts)
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")
            continue
    
    if not all_texts:
        return "No documents were successfully processed"
    
    # Create the Chroma database with all documents
    db = Chroma.from_documents(
        all_texts,
        collection_name="pdf_lib_data",
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    return f"Database created successfully at: {persist_directory} with {len(pdf_files)} PDFs processed and {len(all_texts)} text chunks."
@tool
def search_web(query):
    """Performs a web search using DuckDuckGo and returns text from the top result."""
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all('a', class_='result__a')
        
        if not results:
            return "No results found."
            
        top_result_url = results[0]['href']
        
        page_response = requests.get(top_result_url, headers=headers)
        page_response.raise_for_status()
        page_soup = BeautifulSoup(page_response.text, 'html.parser')
        
        paragraphs = page_soup.find_all('p')
        page_text = "\n".join([p.get_text() for p in paragraphs])
        
        print(f"Web search for '{query}' successful.")
        print(f"Top result URL: {page_text[:100]}")
        return page_text[:500]
    except Exception as e:
        print(f"Error during web search: {e}")
        return f"Error: {e}"
@tool
def calculate_Tax(income: float) -> float:
    """Calculating the tax based on the income."""
    tax_rate = 0.2
    tax = income * tax_rate
    print(f"Calculated Taxx: {tax}")
    return tax

@tool
def retreave_information(query: str) -> str:
    """ Retreaving information from the database based on the query. It uses similarity search to find the most relevant chunks of information."""
    retriver = LoadDataBase(persist_directory="./chroma_db_multilingual", collection_name="audit_documents_better_embeddings").as_retriever(
    search_type="similarity",
    search_kwargs={"k": 1}  # K is the amount of chunks to return
)
    results = retriver.invoke(query)
    print(f"Retreaved Information: {[result.page_content for result in results]} \n \n \n \n \n \n")
    return "\n".join([result.page_content for result in results])
tools = [calculate_Tax, retreave_information, search_web]
llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"), base_url='https://api.openai.com/v1')
llm =llm.bind_tools(tools)
def Agent(state: AgentState) -> AgentState:
    """ The main function of the agent which takes the current state and returns the next state."""
    messages = state["messages"]
    response = llm.invoke(messages)
    new_state = {"messages": messages + [response]}
    return new_state
def sould_continue(state: AgentState) -> bool:
    """ A simple function to check if the agent should continue or not."""
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return False
    return True
def test_llm(message: str) -> None:
    """ A simple test function to check the LLM response."""
    response = llm.invoke([HumanMessage(content=message)])
    print(f"LLM Response: {response}")



graph = StateGraph(AgentState)
tool_node = ToolNode(tools=tools)
graph.add_node("tool_node", tool_node)
graph.add_node("agent_node", Agent)
graph.add_edge(START, "agent_node")
graph.add_conditional_edges(
    "agent_node", 
    sould_continue,
    {
        True: "tool_node",
        False: END
    }
)
graph.add_edge("tool_node", "agent_node")
app = graph.compile()

# System prompt based on the project description
SYSTEM_PROMPT = "you just answer the questions"

initial_state = {"messages": [SystemMessage(content=SYSTEM_PROMPT), 
                              HumanMessage(content="what modle are you exactly, what version are you?")]}
result=app.invoke(initial_state)
print(f"Final Result: {result['messages'][-1].content}")

