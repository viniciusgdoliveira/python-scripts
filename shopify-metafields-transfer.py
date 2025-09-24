"""
shopify_metafields_transfer.py

Single script that does two things:
 1) Export all Products and Collections metafields from a *source* shop to a JSON file.
 2) Import those metafields into a *target* shop, matching resources by handle (product.handle / collection.handle).

Usage examples (after setting up env vars or passing args):
  # Export
  python shopify_metafields_transfer.py export --output metafields.json

  # Import (dry-run)
  python shopify_metafields_transfer.py import --input metafields.json --dry-run

  # Import (apply and overwrite existing namespace+key)
  python shopify_metafields_transfer.py import --input metafields.json --overwrite

Environment variables (alternatively pass via CLI):
  SOURCE_SHOP      example: "source-store.myshopify.com"
  SOURCE_TOKEN     Admin API access token for source store
  TARGET_SHOP      example: "target-store.myshopify.com"
  TARGET_TOKEN     Admin API access token for target store
  API_VERSION      (optional) default: "2024-10"

Important notes & limitations:
 - This script uses the Shopify Admin GraphQL API. Give the custom app / access token read/write access to Products, Collections and Metafields.
 - Mapping is done by handle. The script will look up the target shop's product/collection by the same handle. If handles differ (or item missing), the metafields will be skipped.
 - Some complex metafield types (file references, references to other Shopify IDs, app-specific types) may not copy cleanly. Inspect the exported JSON and test on a development store first.
 - The script tries to update an existing metafield (same namespace+key) when --overwrite is used; otherwise it creates new metafields.

"""

import os
import json
import time
import argparse
import logging
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_API_VERSION = os.environ.get("API_VERSION", "2024-10")


class ShopifyGraphQL:
    def __init__(self, shop: str, token: str, api_version: str = DEFAULT_API_VERSION):
        if not shop:
            raise ValueError("shop must be provided (e.g. 'your-shop.myshopify.com')")
        self.shop = shop
        self.token = token
        self.api_version = api_version
        self.endpoint = f"https://{self.shop}/admin/api/{self.api_version}/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        try:
            resp = requests.post(self.endpoint, headers=self.headers, json=payload)
            if resp.status_code != 200:
                logger.error("GraphQL request failed: %s %s", resp.status_code, resp.text)
                resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                logger.error("GraphQL errors: %s", body["errors"])  # still return body for debugging
            return body
        except Exception as e:
            logger.error("GraphQL request exception: %s", e)
            return None


# ----------------------- Export functions -----------------------

def export_products_metafields(client: ShopifyGraphQL) -> List[Dict[str, Any]]:
    logger.info("Exporting products and their metafields from %s", client.shop)
    products = []
    after = None
    # We'll page products (50 per page). Each product we request metafields(first:250).
    query = """
    query($after: String) {
      products(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            handle
            title
            metafields(first: 250) {
              edges {
                node {
                  id
                  namespace
                  key
                  type
                  value
                }
              }
            }
          }
        }
      }
    }
    """
    while True:
        variables = {"after": after} if after else {}
        body = client.execute(query, variables)
        data = body.get("data", {})
        products_block = data.get("products") if data else None
        if not products_block:
            break
        for edge in products_block["edges"]:
            node = edge["node"]
            mf_list = [
                {"namespace": m["node"]["namespace"], "key": m["node"]["key"], "type": m["node"].get("type"), "value": m["node"].get("value")}
                for m in node.get("metafields", {}).get("edges", [])
            ]
            products.append({"id": node["id"], "handle": node.get("handle"), "title": node.get("title"), "metafields": mf_list})
        page_info = products_block.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
            logger.info("Fetched page, continuing after cursor %s", after)
            time.sleep(0.2)
        else:
            break
    logger.info("Exported %d products", len(products))
    return products


def export_collections_metafields(client: ShopifyGraphQL) -> List[Dict[str, Any]]:
    logger.info("Exporting collections and their metafields from %s", client.shop)
    collections = []
    after = None
    query = """
    query($after: String) {
      collections(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            handle
            title
            metafields(first: 250) {
              edges {
                node {
                  id
                  namespace
                  key
                  type
                  value
                }
              }
            }
          }
        }
      }
    }
    """
    while True:
        variables = {"after": after} if after else {}
        body = client.execute(query, variables)
        data = body.get("data", {})
        block = data.get("collections") if data else None
        if not block:
            break
        for edge in block["edges"]:
            node = edge["node"]
            mf_list = [
                {"namespace": m["node"]["namespace"], "key": m["node"]["key"], "type": m["node"].get("type"), "value": m["node"].get("value")}
                for m in node.get("metafields", {}).get("edges", [])
            ]
            collections.append({"id": node["id"], "handle": node.get("handle"), "title": node.get("title"), "metafields": mf_list})
        page_info = block.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
            logger.info("Fetched page, continuing after cursor %s", after)
            time.sleep(0.2)
        else:
            break
    logger.info("Exported %d collections", len(collections))
    return collections


def export_all(source_shop: str, source_token: str, api_version: str, output_file: str):
    client = ShopifyGraphQL(source_shop, source_token, api_version)
    products = export_products_metafields(client)
    collections = export_collections_metafields(client)
    out = {"products": products, "collections": collections, "exported_at": time.time(), "source_shop": source_shop}
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    logger.info("Saved export to %s", output_file)


# ----------------------- Import functions -----------------------

GET_OWNER_METAFIELDS_QUERY = """
query($id: ID!) {
  node(id: $id) {
    id
    __typename
    ... on Product {
      metafields(first: 250) {
        edges { node { id namespace key type value } }
      }
    }
    ... on Collection {
      metafields(first: 250) {
        edges { node { id namespace key type value } }
      }
    }
  }
}
"""

METAFIELDS_SET_MUTATION = """
mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      id
      namespace
      key
    }
    userErrors {
      field
      message
    }
  }
}
"""

METAFIELD_DEFINITION_CREATE_MUTATION = """
mutation metafieldDefinitionCreate($definition: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $definition) {
    createdDefinition {
      id
      name
      namespace
      key
      type {
        name
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_BY_HANDLE_QUERY = """
query($handle: String!) { productByHandle(handle: $handle) { id } }
"""

COLLECTION_BY_HANDLE_QUERY = """
query($handle: String!) { collectionByHandle(handle: $handle) { id } }
"""

GET_METAFIELD_DEFINITIONS_QUERY = """
query($ownerType: MetafieldOwnerType!) {
  metafieldDefinitions(first: 250, ownerType: $ownerType) {
    edges {
      node {
        id
        name
        namespace
        key
        type {
          name
        }
      }
    }
  }
}
"""


def get_metafield_definitions(client: ShopifyGraphQL, owner_type: str) -> Dict[str, Dict[str, Any]]:
    """Get existing metafield definitions for a given owner type (PRODUCT, COLLECTION, etc.)"""
    body = client.execute(GET_METAFIELD_DEFINITIONS_QUERY, {"ownerType": owner_type})
    definitions = {}
    if body and "data" in body:
        edges = body.get("data", {}).get("metafieldDefinitions", {}).get("edges", [])
        for edge in edges:
            node = edge["node"]
            key = f"{node['namespace']}|{node['key']}"
            definitions[key] = node
    else:
        logger.error("Failed to get metafield definitions for %s: %s", owner_type, body)
    return definitions


def create_metafield_definition(client: ShopifyGraphQL, namespace: str, key: str, name: str, 
                              owner_type: str, type_name: str, dry_run: bool = True) -> Optional[str]:
    """Create a metafield definition if it doesn't exist"""
    
    # Skip restricted namespaces that require special permissions
    # Shopify-owned namespaces typically require special permissions
    if namespace == 'shopify' or namespace.startswith('shopify--'):
        logger.warning("Skipping metafield definition %s|%s - restricted namespace requires special permissions", namespace, key)
        return None
    
    definition_input = {
        "name": name,
        "namespace": namespace,
        "key": key,
        "ownerType": owner_type,
        "type": type_name
    }
    
    logger.info("Creating metafield definition %s|%s for %s", namespace, key, owner_type)
    if not dry_run:
        body = client.execute(METAFIELD_DEFINITION_CREATE_MUTATION, {"definition": definition_input})
        if body is None:
            logger.error("Failed to execute GraphQL request for %s|%s", namespace, key)
            return None
        
        errors = body.get("data", {}).get("metafieldDefinitionCreate", {}).get("userErrors", [])
        if errors:
            logger.error("Definition creation errors for %s|%s: %s", namespace, key, errors)
            return None
        else:
            definition_id = body.get("data", {}).get("metafieldDefinitionCreate", {}).get("createdDefinition", {}).get("id")
            logger.info("Created metafield definition %s|%s with ID: %s", namespace, key, definition_id)
            return definition_id
    else:
        logger.info("DRY RUN: Would create metafield definition %s|%s", namespace, key)
        return "dry_run_id"


def find_target_owner_id(client: ShopifyGraphQL, resource_type: str, handle: str) -> Optional[str]:
    if resource_type == "product":
        logger.debug("Looking up product with handle: %s", handle)
        body = client.execute(PRODUCT_BY_HANDLE_QUERY, {"handle": handle})
        logger.debug("Product lookup response: %s", body)
        if body and "data" in body:
            product_data = body.get("data", {}).get("productByHandle")
            if product_data:
                return product_data.get("id")
            else:
                logger.warning("Product with handle '%s' not found", handle)
                return None
        else:
            logger.error("Failed to get product by handle '%s': %s", handle, body)
            return None
    elif resource_type == "collection":
        logger.debug("Looking up collection with handle: %s", handle)
        body = client.execute(COLLECTION_BY_HANDLE_QUERY, {"handle": handle})
        logger.debug("Collection lookup response: %s", body)
        if body and "data" in body:
            collection_data = body.get("data", {}).get("collectionByHandle")
            if collection_data:
                return collection_data.get("id")
            else:
                logger.warning("Collection with handle '%s' not found", handle)
                return None
        else:
            logger.error("Failed to get collection by handle '%s': %s", handle, body)
            return None
    else:
        return None


def get_existing_metafields_for_owner(client: ShopifyGraphQL, owner_gid: str) -> List[Dict[str, Any]]:
    body = client.execute(GET_OWNER_METAFIELDS_QUERY, {"id": owner_gid})
    node = body.get("data", {}).get("node")
    if not node:
        return []
    edges = []
    mf_block = None
    if node.get("__typename") == "Product":
        mf_block = node.get("metafields", {})
    elif node.get("__typename") == "Collection":
        mf_block = node.get("metafields", {})
    if mf_block:
        edges = mf_block.get("edges", [])
    result = []
    for e in edges:
        n = e["node"]
        result.append({"id": n["id"], "namespace": n["namespace"], "key": n["key"], "type": n.get("type"), "value": n.get("value")})
    return result


def import_metafields(target_shop: str, target_token: str, api_version: str, input_file: str, dry_run: bool = True, overwrite: bool = False):
    client = ShopifyGraphQL(target_shop, target_token, api_version)
    with open(input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    total_definitions_created = 0
    total_metafields_set = 0
    total_skipped = 0

    # Step 1: Collect all unique metafield definitions needed
    logger.info("Step 1: Collecting metafield definitions...")
    product_definitions_needed = set()
    collection_definitions_needed = set()
    
    for prod in payload.get("products", []):
        for mf in prod.get("metafields", []):
            ns = mf.get("namespace")
            key = mf.get("key")
            mtype = mf.get("type", "single_line_text_field")
            product_definitions_needed.add((ns, key, mtype))
    
    for coll in payload.get("collections", []):
        for mf in coll.get("metafields", []):
            ns = mf.get("namespace")
            key = mf.get("key")
            mtype = mf.get("type", "single_line_text_field")
            collection_definitions_needed.add((ns, key, mtype))

    # Step 2: Create metafield definitions
    logger.info("Step 2: Creating metafield definitions...")
    
    # Get existing product definitions
    existing_product_defs = get_metafield_definitions(client, "PRODUCT")
    for ns, key, mtype in product_definitions_needed:
        identifier = f"{ns}|{key}"
        if identifier not in existing_product_defs:
            name = f"{ns} {key}".replace("_", " ").title()
            create_metafield_definition(client, ns, key, name, "PRODUCT", mtype, dry_run)
            total_definitions_created += 1
        else:
            logger.info("Metafield definition %s already exists for products", identifier)
    
    # Get existing collection definitions
    existing_collection_defs = get_metafield_definitions(client, "COLLECTION")
    for ns, key, mtype in collection_definitions_needed:
        identifier = f"{ns}|{key}"
        if identifier not in existing_collection_defs:
            name = f"{ns} {key}".replace("_", " ").title()
            create_metafield_definition(client, ns, key, name, "COLLECTION", mtype, dry_run)
            total_definitions_created += 1
        else:
            logger.info("Metafield definition %s already exists for collections", identifier)

    # Step 3: Set metafield values on products
    logger.info("Step 3: Setting metafield values on products...")
    for prod in payload.get("products", []):
        handle = prod.get("handle")
        if not handle:
            logger.warning("Skipping product with no handle: %s", prod.get("id"))
            total_skipped += 1
            continue
        
        owner_gid = find_target_owner_id(client, "product", handle)
        if not owner_gid:
            logger.warning("Target product with handle '%s' not found. Skipping.", handle)
            total_skipped += 1
            continue

        # Prepare metafields for this product
        metafields_to_set = []
        for mf in prod.get("metafields", []):
            ns = mf.get("namespace")
            key = mf.get("key")
            value = mf.get("value")
            mtype = mf.get("type", "single_line_text_field")
            
            metafield_input = {
                "ownerId": owner_gid,
                "namespace": ns,
                "key": key,
                "value": value,
                "type": mtype
            }
            metafields_to_set.append(metafield_input)

        if metafields_to_set:
            logger.info("Setting %d metafields on product %s", len(metafields_to_set), handle)
            if not dry_run:
                body = client.execute(METAFIELDS_SET_MUTATION, {"metafields": metafields_to_set})
                errors = body.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
                if errors:
                    logger.error("Metafield set errors for product %s: %s", handle, errors)
                else:
                    total_metafields_set += len(metafields_to_set)
            else:
                total_metafields_set += len(metafields_to_set)
            time.sleep(0.2)

    # Step 4: Set metafield values on collections
    logger.info("Step 4: Setting metafield values on collections...")
    for coll in payload.get("collections", []):
        handle = coll.get("handle")
        if not handle:
            logger.warning("Skipping collection with no handle: %s", coll.get("id"))
            total_skipped += 1
            continue
        
        owner_gid = find_target_owner_id(client, "collection", handle)
        if not owner_gid:
            logger.warning("Target collection with handle '%s' not found. Skipping.", handle)
            total_skipped += 1
            continue

        # Prepare metafields for this collection
        metafields_to_set = []
        for mf in coll.get("metafields", []):
            ns = mf.get("namespace")
            key = mf.get("key")
            value = mf.get("value")
            mtype = mf.get("type", "single_line_text_field")
            
            metafield_input = {
                "ownerId": owner_gid,
                "namespace": ns,
                "key": key,
                "value": value,
                "type": mtype
            }
            metafields_to_set.append(metafield_input)

        if metafields_to_set:
            logger.info("Setting %d metafields on collection %s", len(metafields_to_set), handle)
            if not dry_run:
                body = client.execute(METAFIELDS_SET_MUTATION, {"metafields": metafields_to_set})
                errors = body.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
                if errors:
                    logger.error("Metafield set errors for collection %s: %s", handle, errors)
                else:
                    total_metafields_set += len(metafields_to_set)
            else:
                total_metafields_set += len(metafields_to_set)
            time.sleep(0.2)

    logger.info("Import complete: definitions_created=%d metafields_set=%d skipped=%d", 
                total_definitions_created, total_metafields_set, total_skipped)


# ----------------------- CLI -----------------------

def get_env_or_arg(value: Optional[str], env_name: str) -> Optional[str]:
    if value:
        return value
    return os.environ.get(env_name)


def main():
    parser = argparse.ArgumentParser(description="Export/import Shopify product & collection metafields between stores")
    sub = parser.add_subparsers(dest="cmd")

    p_export = sub.add_parser("export", help="Export metafields from a source shop")
    p_export.add_argument("--source-shop", help="source shop domain (eg my-shop.myshopify.com)")
    p_export.add_argument("--source-token", help="source Admin API access token")
    p_export.add_argument("--api-version", default=DEFAULT_API_VERSION)
    p_export.add_argument("--output", default="metafields_export.json")

    p_import = sub.add_parser("import", help="Import metafields into a target shop")
    p_import.add_argument("--target-shop", help="target shop domain (eg target.myshopify.com)")
    p_import.add_argument("--target-token", help="target Admin API access token")
    p_import.add_argument("--api-version", default=DEFAULT_API_VERSION)
    p_import.add_argument("--input", required=True, help="export JSON file path")
    p_import.add_argument("--dry-run", action="store_true", help="Don't apply changes, just simulate")
    p_import.add_argument("--overwrite", action="store_true", help="Update metafields with same namespace+key if present")

    args = parser.parse_args()

    if args.cmd == "export":
        source_shop = get_env_or_arg(args.source_shop, "SOURCE_SHOP")
        source_token = get_env_or_arg(args.source_token, "SOURCE_TOKEN")
        if not source_shop or not source_token:
            logger.error("Please provide --source-shop and --source-token or set SOURCE_SHOP and SOURCE_TOKEN environment variables")
            return
        export_all(source_shop, source_token, args.api_version, args.output)

    elif args.cmd == "import":
        target_shop = get_env_or_arg(args.target_shop, "TARGET_SHOP")
        target_token = get_env_or_arg(args.target_token, "TARGET_TOKEN")
        if not target_shop or not target_token:
            logger.error("Please provide --target-shop and --target-token or set TARGET_SHOP and TARGET_TOKEN environment variables")
            return
        import_metafields(target_shop, target_token, args.api_version, args.input, dry_run=args.dry_run, overwrite=args.overwrite)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
