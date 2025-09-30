# Shopify Python Scripts

A collection of Python scripts for managing Shopify stores using the Shopify Admin GraphQL API.

## Scripts

### 1. Shopify Metafields Transfer (`shopify-metafields-transfer.py`)

Export and import Shopify product and collection metafields between stores.

**Features:**
- **Export metafields**: Export all product and collection metafields from a source Shopify store to a JSON file
- **Import metafields**: Import metafields from a JSON file into a target Shopify store
- **Dry-run mode**: Test imports without making actual changes
- **Overwrite support**: Update existing metafields with the same namespace+key

### 2. Metafields to CSV (`metafields_to_csv.py`)

Convert exported metafields JSON data to CSV format for analysis.

**Features:**
- **CSV conversion**: Convert exported metafields data to CSV format
- **Custom metafields**: Extract all custom namespace metafields as columns
- **Product data**: Include handle, title, and all custom metafields

### 3. Pink Product Tagger (`pink_product_tagger.py`)

Automatically identify and tag pink products based on color metafields.

**Features:**
- **Color detection**: Analyze hex color values to identify pink products
- **Automatic tagging**: Add "rosa" tag to products identified as pink
- **CSV export**: Save product data with color analysis results
- **Dry-run mode**: Test tagging without making actual changes
- **Smart detection**: Only adds tags to products that don't already have "rosa" tag

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
   # For metafields transfer
   SOURCE_SHOP=your-source-shop.myshopify.com
   SOURCE_TOKEN=your-source-access-token
   TARGET_SHOP=your-target-shop.myshopify.com
   TARGET_TOKEN=your-target-access-token
   
   # For pink product tagger
   SOURCE2_SHOP=your-shop.myshopify.com
   SOURCE2_TOKEN=your-access-token
   
   API_VERSION=2024-10
   ```

## Usage

### 1. Metafields Transfer

#### Export Metafields

Export all product and collection metafields from your source store:

```bash
python shopify-metafields-transfer.py export --output metafields.json
```

#### Import Metafields

Import metafields into your target store (dry-run first):

```bash
# Dry-run to see what would be imported
python shopify-metafields-transfer.py import --input metafields.json --dry-run

# Actually import the metafields
python shopify-metafields-transfer.py import --input metafields.json --overwrite
```

### 2. Convert Metafields to CSV

Convert exported metafields to CSV format for analysis:

```bash
python metafields_to_csv.py --input metafields.json --output products.csv
```

### 3. Pink Product Tagger

Identify and tag pink products based on color metafields:

```bash
# Dry-run to see what would be tagged (recommended first)
python pink_product_tagger.py --output products_with_pink_tags.csv --dry-run

# Actually tag pink products
python pink_product_tagger.py --output products_with_pink_tags.csv
```

**Pink Product Tagger Details:**
- Analyzes the `custom.cor` metafield for hex color values
- Uses color detection algorithm to identify pink colors
- Only adds "rosa" tag to products that don't already have it
- Saves detailed CSV with color analysis results
- Requires `SOURCE2_SHOP` and `SOURCE2_TOKEN` environment variables

## Important Notes

### Metafields Transfer
- **Mapping by handle**: The script matches products/collections between stores by their handle. If handles differ or items are missing, those metafields will be skipped.
- **Complex metafield types**: Some complex metafield types (file references, references to other Shopify IDs, app-specific types) may not copy cleanly.
- **Test first**: Always test on a development store before running on production.
- **API limits**: The script includes rate limiting to respect Shopify's API limits.

### Pink Product Tagger
- **Color detection**: Uses RGB analysis to identify pink colors based on specific criteria
- **Metafield requirement**: Requires products to have a `custom.cor` metafield with hex color values
- **Tag management**: Only adds "rosa" tag, never removes existing tags
- **Dry-run recommended**: Always test with `--dry-run` first to see what would be tagged

## Limitations

### Metafields Transfer
- Only supports Products and Collections metafields
- Requires matching handles between source and target stores
- Some complex metafield types may not transfer correctly
- Restricted namespaces (like `shopify`) require special permissions

### Pink Product Tagger
- Only works with hex color values in `custom.cor` metafield
- Color detection algorithm may not catch all pink variations
- Requires products to have the color metafield populated

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).
