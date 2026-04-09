import streamlit as st
from mistralai import Mistral
import config
from query_classifier import classify_question
from deep_analysis import deep_analysis_of_question
from query_generator import generate_multiple_cypher_queries
from query_executor import execute_multiple_queries
from response_generator import synthesize_comprehensive_answer, generate_direct_answer

def process_query_with_deep_reasoning(client, question, conversation_history=None, model_option="Auto (tries multiple)"):

    # PHASE 1: Initial classification
    query_type = classify_question(client, question, model_option)

    if query_type == "DIRECT":
        # Question doesn't require graph search - provide direct answer
        answer = generate_direct_answer(client, question, conversation_history, model_option)
        return answer, "direct", None

    # PHASE 2: Deep analysis of the question
    with st.spinner("Analyzing question deeply..."):
        analysis = deep_analysis_of_question(client, question, conversation_history, model_option)

    # Check if analysis determined no graph search is needed
    if analysis["query_strategy"] == "no_graph_needed" or not analysis["entities"]:
        answer = generate_direct_answer(client, question, conversation_history, model_option)
        return answer, "direct", analysis

    # PHASE 3: Generate multiple strategic queries based on analysis
    with st.spinner("Planning query strategy..."):
        queries_list = generate_multiple_cypher_queries(client, question, analysis, conversation_history, model_option)

    if not queries_list:
        # Fallback to direct answer if no queries generated
        answer = generate_direct_answer(client, question, conversation_history, model_option)
        return answer, "direct", analysis

    # PHASE 4: Execute all queries and collect results
    with st.spinner(f"Executing {len(queries_list)} targeted queries..."):
        query_results = execute_multiple_queries(queries_list)

    if not query_results or all(result['count'] == 0 for result in query_results):
        # No results found - provide direct answer (FALLBACK)
        answer = generate_direct_answer(client, question, conversation_history, model_option)
        return answer, "direct_fallback", {
            "analysis": analysis,
            "queries_executed": len(queries_list),
            "total_results": 0,
            "queries_list": queries_list,    # Transmet les requêtes générées même si 0 résultat
            "query_results": query_results   # Transmet le tableau (vide) des résultats
        }

    # PHASE 5: Synthesize comprehensive answer from all results
    with st.spinner("Synthesizing comprehensive answer..."):
        answer = synthesize_comprehensive_answer(
            client, question, analysis, query_results, conversation_history, model_option
        )

    return answer, "graph_multi_query", {
        "analysis": analysis,
        "queries_executed": len(queries_list),
        "total_results": sum(r['count'] for r in query_results),
        "queries_list": queries_list,        # Transmet les requêtes générées
        "query_results": query_results       # Transmet les données brutes
    }


def initialize_session_state():
    """Initialize Streamlit session state"""
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "Hello! I am your Hetionet Biomedical Assistant with deep reasoning capabilities. I can analyze complex questions about diseases, compounds, genes, anatomy, and their relationships. How can I help you today?"
            }
        ]


def render_sidebar():
    # Render sidebar with configuration and information
    with st.sidebar:
        st.header("Configuration")

        # API Key input
        mistral_api_key = st.text_input(
            "Mistral API Key",
            key="mistral_api_key",
            type="password",
            value=config.MISTRAL_API_KEY
        )
        st.markdown("[Get a free Mistral API Key](https://console.mistral.ai/)")

        # Model selection
        model_option = st.selectbox(
            "Model",
            config.AVAILABLE_MODELS,
            help="Auto mode tries multiple models for best reliability"
        )

        st.divider()

        # Clear conversation button
        if st.button("Clear conversation"):
            st.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "Hello! I am your Hetionet Biomedical Assistant with deep reasoning capabilities. I can analyze complex questions about diseases, compounds, genes, anatomy, and their relationships. How can I help you today?"
                }
            ]
            st.rerun()

        return mistral_api_key, model_option


def display_chat_history():
    # Display chat message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


def handle_user_input(mistral_api_key, model_option):
    # Handle user input and generate response
    if prompt := st.chat_input(
            placeholder="Ask about diseases, compounds, genes, symptoms, or their interactions..."):
        if not mistral_api_key:
            st.error("Please add your Mistral API key in the sidebar to continue.")
            st.stop()

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Generate response with deep reasoning
        with st.chat_message("assistant"):
            try:
                client = Mistral(api_key=mistral_api_key)

                answer, source_type, metadata = process_query_with_deep_reasoning(
                    client,
                    prompt,
                    conversation_history=st.session_state.messages,
                    model_option=model_option
                )

                st.write(answer)

                # Show metadata about the deep reasoning process (Debug Panel)
                if metadata and source_type in ["graph_multi_query", "direct_fallback"]:
                    
                    # Détermine le titre du panneau en fonction du succès ou du fallback
                    panel_title = "🛠️ Developer Debug Panel (Succès)" if source_type == "graph_multi_query" else "🛠️ Developer Debug Panel (Fallback: 0 résultats Neo4j)"
                    
                    with st.expander(panel_title):
                        st.write(f"**Entities identified:** {', '.join(metadata['analysis']['entities'])}")
                        st.write(f"**Query strategy:** {metadata['analysis']['query_strategy']}")
                        st.write(f"**Reasoning:** {metadata['analysis']['reasoning']}")
                        
                        # Affichage des requêtes Cypher
                        if "queries_list" in metadata and metadata["queries_list"]:
                            st.divider()
                            st.markdown("### 🔍 Generated Cypher Queries")
                            for idx, q in enumerate(metadata['queries_list']):
                                st.caption(f"Query {idx + 1} | Purpose: {q.get('purpose', 'N/A')}")
                                st.code(q.get('cypher', ''), language='cypher')
                                
                        # Affichage des résultats bruts (Triplets Neo4j)
                        if "query_results" in metadata:
                            st.divider()
                            st.markdown("### 📊 Neo4j Database Results")
                            for idx, res in enumerate(metadata['query_results']):
                                st.caption(f"Result {idx + 1} | Triplet Count: {res['count']}")
                                if res['count'] > 0:
                                    st.json(res['triplets'])
                                else:
                                    st.warning("Aucune relation trouvée pour cette requête spécifique.")

                # Add assistant response to history
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "capacity" in error_msg.lower():
                    answer = "I'm experiencing high demand right now. Please wait a moment and try again."
                else:
                    answer = "I apologize, but I encountered an error. Please try rephrasing your question."

                st.error(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})


def main():
    # Main application function
    # Page configuration
    st.set_page_config(
        page_title="Hetionet Biomedical Assistant",
        layout="centered"
    )

    st.title("Hetionet Biomedical Assistant")
    st.markdown("*Ask me complex questions - I use deep reasoning to explore the Hetionet Knowledge Graph*")

    # Initialize session state
    initialize_session_state()

    # Render sidebar and get configuration
    mistral_api_key, model_option = render_sidebar()

    # Display chat history
    display_chat_history()

    # Handle user input
    handle_user_input(mistral_api_key, model_option)

if __name__ == "__main__":
    main()