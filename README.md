# YNABify

A YNAB (You Need A Budget) automation bot that helps manage and categorize transactions.

## Features

- **Amazon Transaction Categorization**: Automatically categorize Amazon purchases
- **Venmo Transaction Labeling**: Label and organize Venmo transactions
- **Transaction Creation**: Create new transactions in YNAB

## Getting Started

### Prerequisites

- Python 3.10 or higher
- YNAB Personal Access Token
- YNAB Budget ID

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env`
2. Add your YNAB credentials to the `.env` file

### Usage

```bash
python main.py
```

## License

MIT - See LICENSE file for details
