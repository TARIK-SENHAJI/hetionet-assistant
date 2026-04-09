from neo4j_client import get_neo4j_client

def execute_multiple_queries(queries_list):

    all_results = []
    seen_triplets = set()  # To avoid duplicates

    neo4j_client = get_neo4j_client()

    for query_obj in queries_list:
        purpose = query_obj.get("purpose", "Unknown purpose")
        cypher = query_obj.get("cypher", "")

        if not cypher:
            continue

        # Execute query
        try:
            triplets = neo4j_client.execute_query(cypher)
        except Exception as e:
            # Skip failed queries
            continue

        # Filter out duplicates
        unique_triplets = []
        for triplet in triplets:
            # Create a unique identifier for the triplet
            triplet_id = f"{triplet['source']}|{triplet['relation']}|{triplet['destination']}"
            if triplet_id not in seen_triplets:
                seen_triplets.add(triplet_id)
                unique_triplets.append(triplet)

        if unique_triplets:
            all_results.append({
                "purpose": purpose,
                "triplets": unique_triplets,
                "count": len(unique_triplets)
            })

    return all_results


def deduplicate_triplets(query_results, max_triplets=None):
    # Deduplicate triplets from multiple queries and limit to max_triplets
    unique_triplets = {}

    for result in query_results:
        for triplet in result['triplets']:
            # Create unique key to identify duplicate relationships
            key = f"{triplet['source'].lower()}|{triplet['relation'].lower()}|{triplet['destination'].lower()}"
            reverse_key = f"{triplet['destination'].lower()}|{triplet['relation'].lower()}|{triplet['source'].lower()}"

            # Only add if neither direction exists
            if key not in unique_triplets and reverse_key not in unique_triplets:
                unique_triplets[key] = triplet

    # Convert to list and limit if specified
    triplets_list = list(unique_triplets.values())
    if max_triplets:
        triplets_list = triplets_list[:max_triplets]

    return triplets_list


def format_triplets_for_display(triplets):
    # Format triplets as readable string for UI display
    if not triplets:
        return "No relationships found."

    result = "Knowledge graph findings:\n"
    for i, triplet in enumerate(triplets, 1):
        result += f"{i}. {triplet['source']} → [{triplet['relation']}] → {triplet['destination']}\n"

    return result