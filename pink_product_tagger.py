#!/usr/bin/env python3
"""
pink_product_tagger.py

Script to:
1. Gather product data (handle, title, tags, custom.cor) from Shopify
2. Save to CSV
3. Identify pink products using color detection
4. Add "rosa" tag to pink products
5. Update CSV with new tags

Usage:
    python pink_product_tagger.py --output products.csv
"""

import os
import csv
import json
import time
import argparse
import logging
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
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
                logger.error("GraphQL errors: %s", body["errors"])
            return body
        except Exception as e:
            logger.error("GraphQL request exception: %s", e)
            return None


def is_pink(hex_color: str) -> bool:
    """
    Check if a hex color is in the pink range.
    
    Args:
        hex_color: Hex color string (e.g., "#FFC0CB" or "FFC0CB")
    
    Returns:
        bool: True if the color is considered pink
    """
    if not hex_color:
        return False
    
    # Remove # if present
    hex_color = hex_color.lstrip('#')
    
    # Validate hex color format
    if len(hex_color) != 6:
        return False
    
    try:
        # Convert hex to RGB
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Pink detection criteria
        return (
            r >= 200 and                # strong red
            g <= 200 and                # not too much green
            b >= 120 and                # enough blue
            (r - g) > 30                # red dominates green
        )
    except ValueError:
        logger.warning(f"Invalid hex color format: {hex_color}")
        return False


def get_products_with_metafields(client: ShopifyGraphQL) -> List[Dict[str, Any]]:
    """Fetch all products with their tags and custom.cor metafield."""
    logger.info("Fetching products with tags and custom.cor metafield from %s", client.shop)
    products = []
    after = None
    
    query = """
    query($after: String) {
      products(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            handle
            title
            tags
            metafields(first: 250, namespace: "custom") {
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
            
            # Extract custom.cor metafield
            custom_cor = ""
            metafields = node.get("metafields", {}).get("edges", [])
            for mf_edge in metafields:
                mf_node = mf_edge["node"]
                if mf_node.get("key") == "cor":
                    custom_cor = mf_node.get("value", "")
                    break
            
            # Extract tags as comma-separated string
            tags = node.get("tags", [])
            tags_str = ", ".join(tags) if tags else ""
            
            products.append({
                "id": node["id"],
                "handle": node.get("handle", ""),
                "title": node.get("title", ""),
                "tags": tags_str,
                "custom_cor": custom_cor
            })
        
        page_info = products_block.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
            logger.info("Fetched page, continuing after cursor %s", after)
            time.sleep(0.2)
        else:
            break
    
    logger.info("Fetched %d products", len(products))
    return products


def save_products_to_csv(products: List[Dict[str, Any]], output_file: str) -> None:
    """Save products data to CSV file."""
    logger.info("Saving %d products to %s", len(products), output_file)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['handle', 'title', 'tags', 'custom_cor', 'is_pink', 'updated_tags']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in products:
            # Check if color is pink
            is_pink_color = is_pink(product['custom_cor'])
            
            # Prepare updated tags - ONLY add rosa if product is pink
            current_tags = product['tags']
            updated_tags = current_tags
            
            if is_pink_color and 'rosa' not in current_tags.lower():
                if current_tags:
                    updated_tags = f"{current_tags}, rosa"
                else:
                    updated_tags = "rosa"
            
            writer.writerow({
                'handle': product['handle'],
                'title': product['title'],
                'tags': current_tags,
                'custom_cor': product['custom_cor'],
                'is_pink': is_pink_color,
                'updated_tags': updated_tags
            })
    
    logger.info("Successfully saved products to %s", output_file)


def update_product_tags(client: ShopifyGraphQL, products: List[Dict[str, Any]], dry_run: bool = True) -> None:
    """Update product tags ONLY for pink products."""
    logger.info("Updating tags for pink products only (dry_run=%s)", dry_run)
    
    # GraphQL mutation to update product tags
    update_tags_mutation = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product {
          id
          handle
          tags
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    updated_count = 0
    # Filter ONLY pink products
    pink_products = [p for p in products if is_pink(p['custom_cor'])]
    
    logger.info("Found %d pink products out of %d total products", len(pink_products), len(products))
    
    for product in pink_products:
        current_tags = product['tags']
        
        # Check if rosa tag is already present
        if 'rosa' in current_tags.lower():
            logger.info("Product %s already has 'rosa' tag, skipping", product['handle'])
            continue
        
        # Add rosa tag ONLY to pink products
        if current_tags:
            new_tags = f"{current_tags}, rosa"
        else:
            new_tags = "rosa"
        
        # Convert tags string to array
        tags_array = [tag.strip() for tag in new_tags.split(',') if tag.strip()]
        
        variables = {
            "input": {
                "id": product['id'],
                "tags": tags_array
            }
        }
        
        logger.info("Updating tags for PINK product %s: %s -> %s", 
                   product['handle'], current_tags, new_tags)
        
        if not dry_run:
            body = client.execute(update_tags_mutation, variables)
            if body and "data" in body:
                errors = body.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                if errors:
                    logger.error("Error updating product %s: %s", product['handle'], errors)
                else:
                    updated_count += 1
                    logger.info("Successfully updated PINK product %s", product['handle'])
            else:
                logger.error("Failed to update product %s", product['handle'])
        else:
            updated_count += 1
        
        time.sleep(0.2)  # Rate limiting
    
    logger.info("Updated %d PINK products", updated_count)


def main():
    """Main function to handle command line arguments and execute the process."""
    parser = argparse.ArgumentParser(
        description="Gather product data, identify pink products, and update tags"
    )
    parser.add_argument(
        '--output', '-o',
        default='products_with_pink_tags.csv',
        help='Output CSV file (default: products_with_pink_tags.csv)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Don\'t update product tags, just simulate the process'
    )
    parser.add_argument(
        '--api-version',
        default=DEFAULT_API_VERSION,
        help=f'Shopify API version (default: {DEFAULT_API_VERSION})'
    )
    
    args = parser.parse_args()
    
    # Get credentials from environment
    source_shop = os.environ.get("SOURCE2_SHOP")
    source_token = os.environ.get("SOURCE2_TOKEN")
    
    if not source_shop or not source_token:
        logger.error("Please set SOURCE2_SHOP and SOURCE2_TOKEN environment variables")
        return
    
    try:
        # Initialize Shopify client
        client = ShopifyGraphQL(source_shop, source_token, args.api_version)
        
        # Step 1: Fetch products with metafields
        logger.info("Step 1: Fetching products with tags and custom.cor metafield...")
        products = get_products_with_metafields(client)
        
        if not products:
            logger.warning("No products found")
            return
        
        # Step 2: Save to CSV with pink detection
        logger.info("Step 2: Saving products to CSV with pink detection...")
        save_products_to_csv(products, args.output)
        
        # Step 3: Update tags for pink products
        logger.info("Step 3: Updating tags for pink products...")
        update_product_tags(client, products, dry_run=args.dry_run)
        
        # Summary
        pink_count = sum(1 for p in products if is_pink(p['custom_cor']))
        logger.info("Process completed successfully!")
        logger.info("Summary:")
        logger.info("  - Total products: %d", len(products))
        logger.info("  - Pink products found: %d", pink_count)
        logger.info("  - CSV file saved: %s", args.output)
        if args.dry_run:
            logger.info("  - Mode: DRY RUN (no actual updates made)")
        else:
            logger.info("  - Mode: LIVE (updates applied)")
        
    except Exception as e:
        logger.error("Error during execution: %s", e)
        raise


if __name__ == "__main__":
    main()
