import json
import time
import config

def deep_analysis_of_question(client, question, conversation_history=None, model_option="Auto (tries multiple)"):

    context = _build_conversation_context(conversation_history)

    prompt = f"""You are an expert biomedical analyst. Perform a DEEP ANALYSIS of this question before any database queries.

{context}

User question: "{question}"

Your task: Analyze this question thoroughly and provide a structured analysis in JSON format.

Think step-by-step:
1. What are ALL the biomedical entities mentioned?
2. What relationships or interactions is the user asking about?
3. What is the logical connection between entities?

Hetionet Knowledge Graph structure reminder:
- Nodes: All nodes have the generic label 'Entity'. They have a 'name' property (e.g., 'HAX1', 'Asthma') and a 'kind' property which can be: Anatomy, Compound, Disease, Gene, Symptom, Biological Process, Molecular Function.
- Relations: Specific types like CtD (Compound treats Disease), CbG (Compound binds Gene), DaG (Disease associates Gene), DpS (Disease presents Symptom), etc.

Respond with ONLY valid JSON in this exact format:
{{
  "entities": ["entity1", "entity2", ...],
  "aspects": ["aspect1", "aspect2", ...],
  "relationships_to_explore": ["treats", "binds", "presents", "associates", ...],
  "query_strategy": "single_entity" or "multiple_entities",
  "reasoning": "Brief explanation of your analysis"
}}

Example for "What compounds treat Asthma and what symptoms does it present?":
{{
  "entities": ["Asthma", "compounds", "symptoms"],
  "aspects": ["Asthma to compounds connection", "Asthma to symptoms connection"],
  "relationships_to_explore": ["CtD", "DpS"],
  "query_strategy": "multiple_entities",
  "reasoning": "Question asks about treatments (Compound treats Disease) and symptoms (Disease presents Symptom) for Asthma. Need separate queries to find compounds and symptoms."
}}

If question is NOT about biomedical entities in the graph, return:
{{
  "entities": [],
  "aspects": [],
  "relationships_to_explore": [],
  "query_strategy": "no_graph_needed",
  "reasoning": "Question is about [patient info/general advice], not specific biomedical entities"
}}
"""

    messages = [{'role': 'user', 'content': prompt}]
    models_to_try = _get_models_list(model_option)

    for model in models_to_try:
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                temperature=config.ANALYSIS_TEMPERATURE
            )
            analysis_text = response.choices[0].message.content.strip()

            # Clean up the response to extract JSON
            analysis_text = _extract_json(analysis_text)

            # Parse JSON
            analysis = json.loads(analysis_text)
            return analysis

        except Exception as e:
            if model == models_to_try[-1]:
                # Return default analysis if all models fail
                return {
                    "entities": [],
                    "aspects": [],
                    "relationships_to_explore": [],
                    "query_strategy": "no_graph_needed",
                    "reasoning": "Failed to analyze question"
                }
            time.sleep(1)
            continue


def _build_conversation_context(conversation_history):
    # Build context string from recent conversation history
    if not conversation_history or len(conversation_history) <= 1:
        return ""

    recent_messages = conversation_history[-config.RECENT_MESSAGES_FOR_CONTEXT:]
    context = "Recent conversation context:\n"
    for msg in recent_messages:
        content = msg['content'][:200]
        context += f"{msg['role']}: {content}\n"
    context += "\n"
    return context


def _extract_json(text):
    # Extract and clean JSON from markdown code blocks or raw text
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text


def _get_models_list(model_option):
    # Return list of models to try based on selected option
    if model_option == "Auto (tries multiple)":
        return config.DEFAULT_MODELS
    else:
        return [model_option]