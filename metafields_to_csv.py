#!/usr/bin/env python3
"""
metafields_to_csv.py

Script to read metafields JSON export and convert to CSV format.
Each product becomes a row with handle, title, and all custom metafields as columns.

Usage:
    python metafields_to_csv.py --input metafields_export.json --output products.csv
"""

import json
import csv
import argparse
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_metafields_data(input_file: str) -> Dict[str, Any]:
    """Load metafields data from JSON file."""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data.get('products', []))} products from {input_file}")
        return data
    except FileNotFoundError:
        logger.error(f"File not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise


def extract_custom_metafields(product: Dict[str, Any]) -> Dict[str, str]:
    """Extract custom metafields from a product and return as dict."""
    custom_metafields = {}
    
    metafields = product.get('metafields', [])
    for metafield in metafields:
        if metafield.get('namespace') == 'custom':
            key = metafield.get('key', '')
            value = metafield.get('value', '')
            
            # Create column name in format: product.metafields.custom.{key}
            column_name = f"product.metafields.custom.{key}"
            custom_metafields[column_name] = value
    
    return custom_metafields


def get_all_custom_keys(products: List[Dict[str, Any]]) -> List[str]:
    """Get all unique custom metafield keys across all products."""
    all_keys = set()
    
    for product in products:
        metafields = product.get('metafields', [])
        for metafield in metafields:
            if metafield.get('namespace') == 'custom':
                key = metafield.get('key', '')
                if key:
                    all_keys.add(f"product.metafields.custom.{key}")
    
    return sorted(list(all_keys))


def export_to_csv(data: Dict[str, Any], output_file: str) -> None:
    """Export products data to CSV file."""
    products = data.get('products', [])
    
    if not products:
        logger.warning("No products found in the data")
        return
    
    # Get all possible custom metafield keys
    all_custom_keys = get_all_custom_keys(products)
    
    # Define CSV headers
    headers = ['handle', 'title'] + all_custom_keys
    
    logger.info(f"Found {len(all_custom_keys)} unique custom metafields")
    logger.info(f"Exporting {len(products)} products to {output_file}")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for product in products:
            handle = product.get('handle', '')
            title = product.get('title', '')
            
            # Create row data
            row_data = {
                'handle': handle,
                'title': title
            }
            
            # Add custom metafields
            custom_metafields = extract_custom_metafields(product)
            row_data.update(custom_metafields)
            
            # Write row
            writer.writerow(row_data)
    
    logger.info(f"Successfully exported to {output_file}")


def main():
    """Main function to handle command line arguments and execute the conversion."""
    parser = argparse.ArgumentParser(
        description="Convert metafields JSON export to CSV format"
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input JSON file containing metafields data'
    )
    parser.add_argument(
        '--output', '-o',
        default='products.csv',
        help='Output CSV file (default: products.csv)'
    )
    
    args = parser.parse_args()
    
    try:
        # Load data
        data = load_metafields_data(args.input)
        
        # Export to CSV
        export_to_csv(data, args.output)
        
        logger.info("Conversion completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during conversion: {e}")
        raise


if __name__ == "__main__":
    main()
