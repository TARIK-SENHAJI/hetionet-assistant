import json
import time
import config

def generate_multiple_cypher_queries(client, question, analysis, conversation_history=None,
                                     model_option="Auto (tries multiple)"):

    if analysis["query_strategy"] == "no_graph_needed" or not analysis["entities"]:
        return []

    context = _build_conversation_context(conversation_history)
    entities_text = ", ".join(analysis["entities"])

    prompt = f"""You are a Master AI Data Engineer specialized in routing natural language to Knowledge Graph templates for academic biomedical research. 

{context}

Original question: "{question}"
Entities identified: {entities_text}

Available Templates:

--- BASIC TEMPLATES (Exact Match) ---
1. "explore_specific": Find specific types of entities connected to a main entity. (Requires: 'entity', 'target_kind')
2. "find_connection": Check the direct relationship between two specific entities. (Requires: 'entity1', 'entity2')

--- EXPERT ACADEMIC TEMPLATES (Multi-hop) ---
3. "drug_repurposing": Find compounds targeting genes associated with a disease. (Requires: 'disease')
4. "shared_mechanisms": Find shared nodes between two entities. (Requires: 'entity1', 'entity2', 'shared_kind')
5. "biomarker_discovery": Find genes connected to BOTH a disease and a symptom. (Requires: 'disease', 'symptom')

--- SEMANTIC TEMPLATE (Vector Search) ---
6. "semantic_search": Use this ONLY when the user asks about broad concepts, uses non-medical terms, OR asks in a language other than English (e.g., French). This uses AI embeddings to find conceptually similar nodes in the English database.
   - Parameters: 'concept', 'target_kind'
   - Valid 'target_kind': Anatomy, Compound, Disease, Gene, Symptom.

CRITICAL RULES FOR PARAMETER EXTRACTION:
- For Basic/Expert templates: Extract ONLY the core root keyword in English (e.g., "Parkinson's disease" -> "parkinson").
- For Semantic template ('semantic_search'): You act as a Medical Translator and Query Expander. You MUST transform the user's raw concept into a highly optimized English vector search string using these 3 universal rules:
  1. TRANSLATE: Translate the core meaning into English.
  2. EXPAND: Include both the plain English term AND the strict clinical/medical terminology (synonyms).
  3. CLEAN: Remove conversational filler words (e.g., "I have", "what is", "maladie").
  
CRITICAL RULE FOR TARGET_KIND SELECTION:
- If the user is describing a feeling, an affliction, a condition, or something happening to their body (e.g., "memory loss", "pain", "fever", "confusion"), you MUST set 'target_kind' to "Symptom". Do NOT set it to "Disease". We must find the symptom first to traverse the graph to the disease.
- If the user is describing a bodily organ or location (e.g., "liver", "brain"), set 'target_kind' to "Anatomy".
  
  Universal Examples of your mental process:
  * User: "J'ai du mal à respirer" -> concept: "shortness of breath dyspnea respiratory difficulty"
  * User: "douleur au niveau du ventre" -> concept: "stomach ache abdominal pain gastric"
  * User: "perte de souvenirs" -> concept: "memory loss amnesia cognitive impairment"
  * User: "problème de sucre dans le sang" -> concept: "high blood sugar hyperglycemia diabetes"

Format expected:
{{
  "queries": [
    {{
      "purpose": "Find diseases semantically related to the expanded concept",
      "template_id": "semantic_search",
      "parameters": {{
        "concept": "expanded english medical concepts here",
        "target_kind": "Disease"
      }}
    }}
  ]
}}

RESPOND WITH ONLY VALID JSON, NO MARKDOWN. DO NOT WRITE CYPHER CODE.
"""

    messages = [{'role': 'user', 'content': prompt}]
    models_to_try = _get_models_list(model_option)

    for model in models_to_try:
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                temperature=config.QUERY_GENERATION_TEMPERATURE
            )
            queries_text = response.choices[0].message.content.strip()
            queries_text = _extract_json(queries_text)
            queries_data = json.loads(queries_text)
            
            # NOTE : On passe 'client' pour pouvoir faire l'embedding en direct
            compiled_queries = _compile_cypher_from_templates(client, queries_data.get("queries", []))
            return compiled_queries

        except Exception as e:
            if model == models_to_try[-1]:
                return []
            time.sleep(1)
            continue

def _get_embedding(client, text):
    """Génère le vecteur à la volée pour la recherche sémantique."""
    response = client.embeddings.create(
        model="mistral-embed",
        inputs=[text]
    )
    return response.data[0].embedding

def _compile_cypher_from_templates(client, query_intents):
    compiled = []
    multi_hop_limit = config.MAX_QUERY_RESULTS * 2 

    for intent in query_intents:
        template_id = intent.get("template_id")
        params = intent.get("parameters", {})
        purpose = intent.get("purpose", "Unknown purpose")
        cypher = ""

        # --- TEMPLATE SÉMANTIQUE ---
        if template_id == "semantic_search" and "concept" in params and "target_kind" in params:
            concept = params["concept"]
            kind = params["target_kind"]
            
            # On demande à Mistral de transformer le concept en vecteur
            vector = _get_embedding(client, concept)
            
            # Recherche vectorielle Neo4j avec un FILTRE DE SCORE STRICT
            cypher = f"""
            CALL db.index.vector.queryNodes('entity_embeddings', 5, {vector})
            YIELD node, score
            WHERE node.kind = '{kind}' AND score > 0.75
            MATCH (node)-[r]-(m:Entity)
            RETURN node AS n, r, m
            LIMIT {multi_hop_limit}
            """

        # --- BASIC TEMPLATES ---
        elif template_id == "explore_specific" and "entity" in params and "target_kind" in params:
            e = params["entity"].replace("'", "\\'").lower()
            kind = params["target_kind"]
            cypher = f"MATCH (n:Entity)-[r]-(m:Entity) WHERE toLower(n.name) CONTAINS '{e}' AND m.kind = '{kind}' RETURN n, r, m LIMIT {config.MAX_QUERY_RESULTS}"

        elif template_id == "find_connection" and "entity1" in params and "entity2" in params:
            e1 = params["entity1"].replace("'", "\\'").lower()
            e2 = params["entity2"].replace("'", "\\'").lower()
            cypher = f"MATCH (n:Entity)-[r]-(m:Entity) WHERE toLower(n.name) CONTAINS '{e1}' AND toLower(m.name) CONTAINS '{e2}' RETURN n, r, m LIMIT {config.MAX_QUERY_RESULTS}"

        # --- EXPERT TEMPLATES ---
        elif template_id == "drug_repurposing" and "disease" in params:
            disease = params["disease"].replace("'", "\\'").lower()
            cypher = f"""
            MATCH p = (d:Entity)-[]-(g:Entity {{kind: 'Gene'}})-[]-(c:Entity {{kind: 'Compound'}}) 
            WHERE toLower(d.name) CONTAINS '{disease}' 
            UNWIND relationships(p) AS r 
            RETURN startNode(r) AS n, r, endNode(r) AS m 
            LIMIT {multi_hop_limit}
            """

        elif template_id == "shared_mechanisms" and "entity1" in params and "entity2" in params and "shared_kind" in params:
            e1 = params["entity1"].replace("'", "\\'").lower()
            e2 = params["entity2"].replace("'", "\\'").lower()
            kind = params["shared_kind"]
            cypher = f"""
            MATCH p = (e1:Entity)-[]-(shared:Entity {{kind: '{kind}'}})-[]-(e2:Entity) 
            WHERE toLower(e1.name) CONTAINS '{e1}' AND toLower(e2.name) CONTAINS '{e2}' 
            UNWIND relationships(p) AS r 
            RETURN startNode(r) AS n, r, endNode(r) AS m 
            LIMIT {multi_hop_limit}
            """

        elif template_id == "biomarker_discovery" and "disease" in params and "symptom" in params:
            disease = params["disease"].replace("'", "\\'").lower()
            symptom = params["symptom"].replace("'", "\\'").lower()
            cypher = f"""
            MATCH p = (d:Entity)-[]-(g:Entity {{kind: 'Gene'}})-[]-(s:Entity {{kind: 'Symptom'}}) 
            WHERE toLower(d.name) CONTAINS '{disease}' AND toLower(s.name) CONTAINS '{symptom}' 
            UNWIND relationships(p) AS r 
            RETURN startNode(r) AS n, r, endNode(r) AS m 
            LIMIT {multi_hop_limit}
            """

        if cypher:
            clean_cypher = " ".join(cypher.split())
            compiled.append({
                "purpose": purpose,
                "cypher": clean_cypher
            })
            
    return compiled

def _build_conversation_context(conversation_history):
    if not conversation_history or len(conversation_history) <= 1:
        return ""
    recent_messages = conversation_history[-config.RECENT_MESSAGES_FOR_CONTEXT:]
    context = "Recent conversation:\n"
    for msg in recent_messages:
        content = msg['content'][:200]
        context += f"{msg['role']}: {content}\n"
    return context + "\n"

def _extract_json(text):
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text

def _get_models_list(model_option):
    if model_option == "Auto (tries multiple)":
        return config.DEFAULT_MODELS
    else:
        return [model_option]