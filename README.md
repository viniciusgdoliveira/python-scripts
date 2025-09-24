# Shopify Metafields Transfer

A Python script for exporting and importing Shopify product and collection metafields between stores using the Shopify Admin GraphQL API.

## Features

- **Export metafields**: Export all product and collection metafields from a source Shopify store to a JSON file
- **Import metafields**: Import metafields from a JSON file into a target Shopify store
- **CSV conversion**: Convert exported metafields data to CSV format for analysis
- **Dry-run mode**: Test imports without making actual changes
- **Overwrite support**: Update existing metafields with the same namespace+key

## Requirements

- Python 3.7+
- Shopify Admin API access tokens for source and target stores
- Required permissions: Products, Collections, and Metafields read/write access

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Copy `env.example` to `.env`:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` with your Shopify store credentials:
   ```
   SOURCE_SHOP=your-source-shop.myshopify.com
   SOURCE_TOKEN=your-source-access-token
   TARGET_SHOP=your-target-shop.myshopify.com
   TARGET_TOKEN=your-target-access-token
   API_VERSION=2024-10
   ```

## Usage

### Export Metafields

Export all product and collection metafields from your source store:

```bash
python shopify-metafields-transfer.py export --output metafields.json
```

### Import Metafields

Import metafields into your target store (dry-run first):

```bash
# Dry-run to see what would be imported
python shopify-metafields-transfer.py import --input metafields.json --dry-run

# Actually import the metafields
python shopify-metafields-transfer.py import --input metafields.json --overwrite
```

### Convert to CSV

Convert exported metafields to CSV format for analysis:

```bash
python metafields_to_csv.py --input metafields.json --output products.csv
```

## Important Notes

- **Mapping by handle**: The script matches products/collections between stores by their handle. If handles differ or items are missing, those metafields will be skipped.
- **Complex metafield types**: Some complex metafield types (file references, references to other Shopify IDs, app-specific types) may not copy cleanly.
- **Test first**: Always test on a development store before running on production.
- **API limits**: The script includes rate limiting to respect Shopify's API limits.

## Limitations

- Only supports Products and Collections metafields
- Requires matching handles between source and target stores
- Some complex metafield types may not transfer correctly
- Restricted namespaces (like `shopify`) require special permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).
