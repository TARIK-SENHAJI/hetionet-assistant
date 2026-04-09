import time
import config
from query_executor import deduplicate_triplets, format_triplets_for_display

def synthesize_comprehensive_answer(client, question, analysis, query_results, conversation_history=None,
                                    model_option="Auto (tries multiple)"):

    if not query_results:
        return "Je n'ai pas trouvé d'informations spécifiques dans le graphe de connaissances (Hetionet) pour ces entités. Essayez de reformuler avec des noms précis de gènes, composés ou maladies."

    # Deduplicate and limit triplets
    triplets_list = deduplicate_triplets(query_results, config.MAX_TRIPLETS_FOR_SYNTHESIS)

    # Prepare concise results summary
    results_text = format_triplets_for_display(triplets_list)

    context = _build_conversation_context(conversation_history)

    prompt = f"""You are an expert biomedical AI assistant. Synthesize a CONCISE, CLEAR, and MEDICAL answer from the knowledge graph data provided below.

{context}

Original question: "{question}"

Entities identified: {', '.join(analysis['entities'])}

{results_text}

---
EXHAUSTIVE HETIONET RELATIONSHIP DICTIONARY:
- CtD (Compound treats Disease): The compound is an approved curative treatment.
- CpD (Compound palliates Disease): The compound manages symptoms but does not cure the disease.
- DaG (Disease associates Gene): The gene is genetically associated with the disease risk.
- DdG (Disease downregulates Gene): The disease causes a decrease in the gene's expression.
- CbG (Compound binds Gene): The compound physically binds to the gene/protein (target).
- CuG (Compound upregulates Gene): The compound increases the gene's expression.
- DpS (Disease presents Symptom): The disease manifests this clinical symptom.
- DlA (Disease localizes to Anatomy): The disease primarily affects this specific anatomical region.
- GiG (Gene interacts Gene): These genes/proteins biologically interact with each other.
- AdG (Anatomy downregulates Gene): This anatomical tissue downregulates the expression of this gene.
- GpMF (Gene participates Molecular Function): The gene/protein is involved in this specific molecular function.
- DrD (Disease resembles Disease): These two diseases share significant similarities.
- CrC (Compound resembles Compound): These two compounds are structurally or chemically similar.
---

CRITICAL REQUIREMENTS for your answer:
1. STRICT GROUNDING: You MUST base your answer EXCLUSIVELY on the provided knowledge graph data above. DO NOT add medications, genes, or facts from your pre-trained knowledge that are not listed in the data.
2. DECODE THE ACRONYMS: Never show the raw acronyms (like CtD, GpMF) to the user. Translate them into clear medical explanations.
3. CATEGORIZE SMARTLY: Explicitly classify the data. If the data only shows "CpD" (palliates) and no "CtD" (treats), explicitly state that the graph only found palliative symptom-management drugs for this condition. Name the specific compounds found in the data (e.g., Pramipexole, Tolcapone).
4. DIRECT ANSWER: Provide a direct answer to the user's question in the very first sentence.

Respond in the same language as the user's question.

Your concise, expert answer:"""

    messages = [{'role': 'user', 'content': prompt}]
    models_to_try = _get_models_list(model_option)

    for model in models_to_try:
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                temperature=config.SYNTHESIS_TEMPERATURE
            )
            answer = response.choices[0].message.content.strip()

            # Post-processing: Remove common redundant patterns
            answer = _clean_answer(answer)

            return answer
        except Exception as e:
            if model == models_to_try[-1]:
                return "Found relevant information but had trouble formulating the response. Please try rephrasing your question."
            time.sleep(1)
            continue


def generate_direct_answer(client, question, conversation_history=None, model_option="Auto (tries multiple)"):
    # Generate direct answer for general questions (no graph search or fallback if graph is empty)
    context = _build_extended_conversation_context(conversation_history)

    prompt = f"""You are a knowledgeable and empathetic biomedical AI assistant. 

{context}

User's message: {question}

Instructions:
- Provide clear medical, biological, or pharmacological information based on your general knowledge.
- If it's a personal situation: Be supportive and recommend consulting healthcare professionals.
- If it's a greeting or thanks: Respond naturally and warmly.
- Keep responses concise (2-4 sentences) and professional.
- Respond in the same language as the user.
- DO NOT mention being specialized in breast cancer. You are a general expert in biomedicine (Hetionet).

Your response:"""

    messages = [{'role': 'user', 'content': prompt}]
    models_to_try = _get_models_list(model_option)

    for model in models_to_try:
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                temperature=config.DIRECT_ANSWER_TEMPERATURE
            )
            return response.choices[0].message.content
        except Exception as e:
            if model == models_to_try[-1]:
                return "I apologize, but I'm having trouble processing your question right now. Please try again in a moment."
            time.sleep(1)
            continue


def _build_conversation_context(conversation_history):
    # Build short context string from recent conversation history
    if not conversation_history or len(conversation_history) <= 1:
        return ""

    recent_messages = conversation_history[-config.RECENT_MESSAGES_FOR_CONTEXT:]
    context = "\n\nPrevious conversation:\n"
    for msg in recent_messages:
        content = msg['content'][:200]
        context += f"{msg['role'].title()}: {content}\n"

    return context


def _build_extended_conversation_context(conversation_history):
    # Build extended context string with more conversation history
    if not conversation_history or len(conversation_history) <= 1:
        return ""

    recent_messages = conversation_history[-config.MAX_CONVERSATION_HISTORY:]
    context = "\n\nConversation history:\n"
    for msg in recent_messages:
        content = msg['content'][:300]
        context += f"{msg['role'].title()}: {content}\n"

    return context


def _clean_answer(answer):
    # Remove redundant phrases like "According to the data" from answer
    redundant_phrases = [
        "According to the knowledge graph, ",
        "The data shows that ",
        "Based on the relationships, ",
        "The results indicate that ",
        "According to the data, ",
        "The information shows that "
    ]

    for phrase in redundant_phrases:
        answer = answer.replace(phrase, "")

    return answer


def _get_models_list(model_option):
    # Return list of models to try based on selected option
    if model_option == "Auto (tries multiple)":
        return config.DEFAULT_MODELS
    else:
        return [model_option]