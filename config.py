import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Neo4j Configuration

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Mistral AI Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# Model Options
AVAILABLE_MODELS = [
    "Auto (tries multiple)",
    "mistral-small-latest",
    "open-mistral-7b",
    "open-mistral-8x7b"
]

# Default models to try in auto mode
DEFAULT_MODELS = ["open-mistral-7b", "open-mistral-8x7b", "mistral-small-latest"]

# Query Limits
MAX_QUERY_RESULTS = 15
MAX_TRIPLETS_FOR_SYNTHESIS = 20
MAX_QUERIES_PER_QUESTION = 4

# Conversation Settings
MAX_CONVERSATION_HISTORY = 6
RECENT_MESSAGES_FOR_CONTEXT = 4

# Temperature Settings
CLASSIFICATION_TEMPERATURE = 0
ANALYSIS_TEMPERATURE = 0.3
QUERY_GENERATION_TEMPERATURE = 0.2
SYNTHESIS_TEMPERATURE = 0.3
DIRECT_ANSWER_TEMPERATURE = 0.5