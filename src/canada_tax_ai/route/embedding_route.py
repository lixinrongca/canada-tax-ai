# router/embedding_router.py
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger
import numpy as np


# ------------------------------------------------------------------ #
#  Route definitions — each route has a name + example phrases
# ------------------------------------------------------------------ #
ROUTES = {
    "tax_calculation": {
        "description": "Calculate tax, compute refund, tax owing, CPP, EI deductions",
        "examples": [
            "calculate my tax return",
            "how much tax do I owe",
            "what is my refund",
            "compute my federal tax",
            "how much CPP did I contribute",
            "calculate EI premiums",
            "what are my deductions",
            "net income calculation",
            "how much will I get back from CRA",
            "what is my total tax payable",
            "compute my provincial tax",
            "how much income tax was deducted",
            "calculate my net income after tax",
            "what is my marginal tax rate",
            "how much is my basic personal amount credit",
            "calculate my taxable income",
            "what is my combined federal and provincial tax",
            "how much CPP2 do I owe",
            "compute my dividend gross-up",
            "what is my after-tax income",
            "how much RRSP can I deduct this year",
            "calculate my pension adjustment",
            "what is my balance owing to CRA",
            "how much was withheld from my paycheque",
            "compute my employment income",
            "what credits can reduce my tax",
            "calculate my charitable donation credit",
            "how much is my tuition tax credit worth",
            "what is my medical expense credit",
            "figure out my tax situation"
        ]
    },

    "document_upload": {
        "description": "Upload T4, T5, tax slips, PDF, image files",
        "examples": [
            "upload my T4",
            "here is my tax slip",
            "I have a T5 to upload",
            "attach my PDF",
            "process this image",
            "scan my tax document",
            "analyze this file",
            "extract data from my slip",
            "I want to submit my T4",
            "here is a photo of my tax slip",
            "please read this document",
            "I am uploading my employment income slip",
            "process my investment income statement",
            "here is my T4A",
            "upload my RL-1 slip",
            "I have my T3 ready to upload",
            "scan this T5 for me",
            "extract numbers from this PDF",
            "read my tax form",
            "I took a picture of my T4",
            "analyze my bank statement slip",
            "upload income slip from my employer",
            "here is my year end tax document",
            "process this CRA form",
            "I want to add another slip",
            "upload second T4 from my part time job",
            "here is the file",
            "read this jpeg",
            "analyze this png",
            "submit my tax document"
        ]
    },

    "tax_slips": {
        "description": "User requests to retrieve, view, or query information from uploaded or stored tax slips such as T4, T5, and other tax documents",
        "examples": [
            "Show my tax slips",
            "Can I see my T4?",
            "Do you have my T4 slip?",
            "Retrieve my T5 slips",
            "What tax slips do you have for me?",
            
            "List all my tax documents",
            "What slips are available for this year?",
            "Do I have any T4s uploaded?",
            "Show me my T5 summary",
            "Find my income slips",
            
            "What income information do you have from my slips?",
            "Can you display my employment income slip?",
            "What does my T4 say?",
            "Summarize my T4 information",
            
            "Do you have my tax documents for 2024?",
            "Show my tax slips for last year",
            "What slips were submitted this year?",
            
            "Retrieve my tax forms",
            "Access my uploaded tax slips",
            "Pull up my tax documents",
            
            "Do I have multiple T4 slips?",
            "How many tax slips do I have?",
            "Are there any missing tax slips?",
            
            "Show my government tax forms",
            "What CRA slips do you have for me?",
            
            "Can you summarize my tax slip data?",
            "Give me an overview of my T4 and T5",
            "What income records are in my tax slips?",
            
            "Check my employer tax slip",
            "Do you have my bank T5 slip?",
            "Show investment income slips",
            
            "What earnings are shown on my T4?",
            "How much income is reported on my slips?",
            
            "Find my most recent tax slip",
            "What is my latest T4?",
            "Do you have updated tax documents?",
            
            "Display all uploaded tax forms",
            "What documents have I submitted for taxes?",
            
            "Can I view my tax slip details?",
            "Let me see my tax records",
            "Open my tax slips section"
        ]
    },

    "tax_policy": {
        "description": "Canadian tax rules, CRA policies, deadlines, RRSP limits",
        "examples": [
            "what is the RRSP contribution limit",
            "when is the tax deadline",
            "what are the tax brackets",
            "explain the basic personal amount",
            "what is the CPP contribution rate",
            "how does EI work",
            "what can I deduct",
            "explain dividend tax credit",
            "CRA rules for home office",
            "what is the TFSA contribution room for 2025",
            "when is the RRSP deadline",
            "how are capital gains taxed in Canada",
            "what is the federal tax rate for my income",
            "explain the working income tax benefit",
            "what is the Manitoba provincial tax rate",
            "how does the dividend gross-up work",
            "what is the age amount credit",
            "can I claim my rent on taxes",
            "how do I report foreign income",
            "what is the disability tax credit",
            "explain the pension income splitting rules",
            "what are eligible medical expenses",
            "CRA rules for RRSP withdrawals",
            "how does the first home buyers plan work",
            "what is the lifetime capital gains exemption",
            "how do I claim union dues",
            "explain the Canada workers benefit",
            "what is the minimum tax rate in Canada",
            "how are T5 dividends taxed",
            "what is the OAS clawback threshold",
            "explain non-refundable tax credits",
            "how does income splitting work for couples",
            "what is the employment expense deduction",
            "CRA rules for cryptocurrency",
            "how are RRIF withdrawals taxed"
        ]
    },

    "user_profile": {
        "description": "Get personal information, SIN, address, marital status, province, dependents, etc. when use inquiries about their profile",
        "examples": [
            "What information do you have about me?",
            "Can I see my profile details?",
            "Show me my personal information",
            "What data is stored under my account?",
            "Give me a summary of my profile",
            "What does my profile contain?",
            "Let me view my account information",
            "What details are on file for me?",
            
            "What is my current address?",
            "What address do you have for me?",
            "Where am I listed as living?",
            "What is my mailing address?",
            
            "Do you have my SIN?",
            "Is my SIN stored in the system?",
            "Can I view my SIN number?",
            
            "What is my marital status?",
            "Am I registered as married or single?",
            "How is my relationship status recorded?",
            
            "How many dependents do I have?",
            "Are any dependents listed under my name?",
            "Tell me about my dependents",
            
            "What province am I registered in?",
            "Which province is on my profile?",
            "Where am I registered?",
            
            "What contact details are saved for me?",
            "What email is linked to my account?",
            "Do you have my phone number?",
            
            "What identity details are recorded for me?",
            "What personal identifiers are associated with me?",
            
            "Can I see all my stored personal data?",
            "What personal records are tied to my account?",
            "Show me everything you have on file for me",
            
            "Is my profile complete?",
            "What information is missing from my profile?",
            
            "What family information is included in my profile?",
            "Is my spouse listed in my account?",
            
            "Do you have any previous addresses for me?",
            "What historical data do you keep about me?",
            
            "What verification details are recorded for me?",
            "Is any of my profile information verified?",
            
            "What info do you got on me?",
            "Let me check my details",
            "What do you have saved about me?"
        ]
    },

    "report_generation": {
        "description": "Generate PDF report, download tax summary, export results",
        "examples": [
            "generate my tax report",
            "download PDF",
            "export my return",
            "create tax summary",
            "print my results",
            "save my tax file",
            "give me a PDF of my tax return",
            "I want to download my assessment",
            "create a summary of my taxes",
            "export my results to PDF",
            "generate a tax report for my records",
            "save my tax calculation",
            "produce my tax document",
            "I need a copy of my return",
            "download my refund summary",
            "create printable tax report",
            "export my T1 general",
            "generate assessment notice",
            "I want a document I can submit",
            "save results as PDF",
            "create my notice of assessment",
            "download tax breakdown",
            "I need proof of my tax filing",
            "generate income summary report",
            "export my credits and deductions",
            "make a PDF with all my tax info",
            "I want to print this",
            "give me something I can send to my accountant",
            "generate year end tax statement",
            "create downloadable report"
        ]
    },

    "general_chat": {
        "description": "Update, collect personal info, or answer general questions that don't fit other routes",
        "examples": [
            "hello",
            "hi",
            "hey there",
            "good morning",
            "good evening",
            
            "can you help me",
            "I need help",
            "help me out",
            "I need assistance",
            
            "what can you do",
            "what does this app do",
            "how does this work",
            "how do I use this",
            "what am I supposed to do here",
            
            "I don't understand",
            "I dont understand",
            "I do not understand",
            "this is confusing",
            "can you explain this",
            "explain it to me",
            "why is this happening",
            
            "where do I start",
            "what should I do first",
            "guide me through this",
            "can you walk me through it",
            "what are my options",
            
            "I am new here",
            "this is my first time",
            "I’ve never used this before",
            "I have never used this before",
            
            "how long will this take",
            "what do you need from me",
            "what information do I need to provide",
            
            "is my data safe",
            "is this secure",
            "how do you handle my data",
            
            "start over",
            "reset",
            "go back",
            "undo that",
            "I made a mistake",
            
            "thank you",
            "thanks",
            "appreciate it",
            "that was helpful",
            
            "bye",
            "goodbye",
            "see you later",
            "I’m done for now",
            "I am done for now",
            "Iam done for now",
            
            "log out",
            "sign out",
            
            "can you show me what you can do",
            "what features are available",
            "what can I do here"
        ]
    }
}

_router = None

class EmbeddingRouter:
    """
    Routes user messages to the correct handler
    using semantic similarity against route examples.
    """

    def __init__(self, threshold: float = 0.48):
        self.threshold = threshold  # min similarity to match a route
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self._route_embeddings: dict[str, np.ndarray] = {}
        self._build_index()

    # ------------------------------------------------------------------ #
    #  Build embedding index from route examples
    # ------------------------------------------------------------------ #
    def _build_index(self):
        logger.info("Building embedding router index...")
        for route_name, route_def in ROUTES.items():
            examples = route_def["examples"]
            vecs = self.embeddings.embed_documents(examples)
            # Store mean vector as route centroid
            self._route_embeddings[route_name] = np.mean(vecs, axis=0)
            logger.debug(f"Indexed route: {route_name} ({len(examples)} examples)")
        logger.success(f"Router index built — {len(ROUTES)} routes")

    # ------------------------------------------------------------------ #
    #  Route a single message
    # ------------------------------------------------------------------ #
    def route(self, message: str) -> dict:
        """
        Returns:
            {
                "route":       "tax_calculation",
                "confidence":  0.87,
                "scores":      {"tax_calculation": 0.87, "general": 0.32, ...},
                "description": "Calculate tax, compute refund..."
            }
        """
        query_vec = np.array(self.embeddings.embed_query(message)).reshape(1, -1)

        scores = {}
        for route_name, centroid in self._route_embeddings.items():
            sim = cosine_similarity(query_vec, centroid.reshape(1, -1))[0][0]
            scores[route_name] = float(sim)

        best_route = max(scores, key=scores.get)
        confidence = scores[best_route]

        # Fall back to general if below threshold, default route is "general_chat"
        if confidence < self.threshold:
            best_route = "general_chat"

        logger.info(
            f"Route: '{message[:60]}' → {best_route} "
            f"(confidence={confidence:.2f})"
        )

        return {
            "route":       best_route,
            "confidence":  confidence,
            "scores":      scores,
            "description": ROUTES[best_route]["description"],
        }

    def route_batch(self, messages: list[str]) -> list[dict]:
        """Route multiple messages at once."""
        return [self.route(m) for m in messages]
    
def _get_router():
    global _router
    if _router is None:
        _router = EmbeddingRouter()
    return _router

def cosine_similarity_router(user_input: str) -> str:
    router = _get_router()
    result = router.route(user_input)
    return result["route"]