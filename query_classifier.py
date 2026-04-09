import time
import config

def classify_question(client, question, model_option="Auto (tries multiple)"):
    prompt = f"""Analyze this user question and classify it:

Question: "{question}"

Classification rules:
- GRAPH: Question explicitly asks about specific scientific or medical entities from the Hetionet knowledge graph:
  * Genes (e.g., HAX1, BRCA1)
  * Compounds / Drugs
  * Diseases
  * Symptoms
  * Anatomy (body parts)
  * Biological Processes or Molecular Functions
  Examples: "What genes are associated with Asthma?", "What compounds treat hypertension?", "What diseases present with fever?", "Tell me about the HAX1 gene"

- DIRECT: Everything else including:
  * Patient information (age, diagnosis, personal situations)
  * General advice or conversational messages (greetings, thanks)
  * General questions without naming specific entities
  Examples: "The patient is 55", "What is a balanced diet?", "Hello!"

RESPOND WITH ONLY: "GRAPH" or "DIRECT"
"""

    messages = [{'role': 'user', 'content': prompt}]
    models_to_try = _get_models_list(model_option)

    for model in models_to_try:
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                temperature=config.CLASSIFICATION_TEMPERATURE
            )
            classification = response.choices[0].message.content.strip().upper()
            return "GRAPH" if "GRAPH" in classification else "DIRECT"
        except Exception:
            if model == models_to_try[-1]:
                return "DIRECT" 
            time.sleep(1)
            continue

    return "DIRECT"

def _get_models_list(model_option):
    if model_option == "Auto (tries multiple)":
        return config.DEFAULT_MODELS
    else:
        return [model_option]