import config
from mistralai import Mistral
from neo4j import GraphDatabase
from tqdm import tqdm
import time

def populate_embeddings():
    mistral = Mistral(api_key=config.MISTRAL_API_KEY)
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))
    
    print("Récupération des nœuds sans embedding...")
    
    get_nodes_query = """
    MATCH (n:Entity) 
    WHERE n.embedding IS NULL 
    RETURN elementId(n) AS node_id, n.name AS name
    """
    
    with driver.session() as session:
        result = session.run(get_nodes_query)
        nodes = [{"node_id": record["node_id"], "name": record["name"]} for record in result]
    
    if not nodes:
        print("Tous les nœuds ont déjà leurs embeddings !")
        driver.close()
        return

    print(f"{len(nodes)} nœuds à traiter. Début de la vectorisation par lots (batch)...")
    
    # Taille du lot : on envoie 50 mots d'un coup à Mistral
    batch_size = 50 
    
    for i in tqdm(range(0, len(nodes), batch_size)):
        batch = nodes[i:i+batch_size]
        names = [node["name"] for node in batch]
        
        success = False
        while not success:
            try:
                # 1. Demande de vecteurs en lot (1 seul appel API pour 50 mots !)
                response = mistral.embeddings.create(
                    model="mistral-embed",
                    inputs=names
                )
                
                # 2. Mise à jour dans Neo4j
                with driver.session() as session:
                    for j, node in enumerate(batch):
                        vector = response.data[j].embedding
                        update_query = """
                        MATCH (n:Entity) WHERE elementId(n) = $node_id
                        SET n.embedding = $vector
                        """
                        session.run(update_query, node_id=node["node_id"], vector=vector)
                
                success = True
                time.sleep(1) # Petite courtoisie d'1 seconde pour soulager l'API
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Rate limit" in error_str:
                    print(f"\n[Rate Limit] API surchargée, pause de 10 secondes...")
                    time.sleep(10) # On attend avant de réessayer le même lot
                else:
                    print(f"\nErreur inattendue: {e}")
                    success = True # On ignore l'erreur et on passe au lot suivant
                    
    driver.close()
    print("\nOpération terminée pour ce lot !")

if __name__ == "__main__":
    populate_embeddings()