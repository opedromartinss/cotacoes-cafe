#!/usr/bin/env python3
"""
Scraper and updater for coffee prices.

This script fetches the latest coffee prices for Arábica and Robusta (Conilon)
from the Notícias Agrícolas widgets and writes the results into JSON
files used by the site.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, List

from bs4 import BeautifulSoup
import requests

# Define custom headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36"
}


def parse_price(url: str) -> Tuple[str, float]:
    """Fetch a price table from Notícias Agrícolas and return the date and price."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tbody = soup.find("tbody")
    row = tbody.find("tr")
    cols = row.find_all("td")
    date_str = cols[0].get_text(strip=True)
    price_str = cols[1].get_text(strip=True).replace(".", "").replace(",", ".")
    price = float(price_str)
    return date_str, price


def is_market_open() -> bool:
    """Return True if the market is open (weekday)."""
    return datetime.now().weekday() < 5


def update_prices(prices_path: Path, price_arabica: float, price_conilon: float,
                  trade_date: str, now: datetime) -> None:
    data = {
        "ultima_atualizacao": now.isoformat(),
        "mercado_fechado": not is_market_open(),
        "data_referencia": trade_date,
        "arabica": price_arabica,
        "conilon": price_conilon,
    }
    prices_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def update_history(history_path: Path,
                   price_arabica: float,
                   price_conilon: float,
                   trade_date: str,
                   now: datetime) -> None:
    """
    Append the latest coffee prices to the historical JSON file.

    Each update creates two records—one for Arábica and one for Conilon—to match
    the original data structure used by the site.  Each record includes the date
    the price refers to (``referente_a``), the exact timestamp when the data was
    collected (``coletado_em``), the product, the type, the price value, the
    measurement unit and the currency.  The history retains only the most
    recent 20 entries (10 updates × 2 types) to prevent unbounded growth.
    """
    # Load existing history if present
    history: List[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
        except json.JSONDecodeError:
            # If the file is malformed, start with an empty list
            history = []

    # Prepare two entries: one for Arabica and another for Conilon
    base_timestamp = now.isoformat()
    arabica_entry = {
        "referente_a": trade_date,
        "coletado_em": base_timestamp,
        "produto": "cafe",
        "tipo": "arabica",
        "valor": price_arabica,
        "unidade": "saca",
        "moeda": "BRL",
    }
    conilon_entry = {
        "referente_a": trade_date,
        "coletado_em": base_timestamp,
        "produto": "cafe",
        "tipo": "conilon",
        "valor": price_conilon,
        "unidade": "saca",
        "moeda": "BRL",
    }

    # Append the new entries to history
    history.append(arabica_entry)
    history.append(conilon_entry)

    # Keep only the last 20 records (10 most recent updates)
    history = history[-20:]

    # Write back to file
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def update_index_html(index_path: Path, arabica_price: float, conilon_price: float) -> None:
    """Inject the latest prices into index.html (if present)."""
    if not index_path.exists():
        return
    html = index_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    def format_brl(value: float) -> str:
        return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    arabica_elem = soup.find(id="preco-arabica")
    if arabica_elem:
        arabica_elem.string = format_brl(arabica_price)
    robusta_elem = soup.find(id="preco-robusta")
    if robusta_elem:
        robusta_elem.string = format_brl(conilon_price)
    index_path.write_text(str(soup), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    prices_path = data_dir / "prices.json"
    history_path = data_dir / "precos.json"
    index_path = root / "index.html"

    arabica_url = "https://www.noticiasagricolas.com.br/widgets/cotacoes?id=29"
    conilon_url = "https://www.noticiasagricolas.com.br/widgets/cotacoes?id=31"

    date_arabica, price_arabica = parse_price(arabica_url)
    date_conilon, price_conilon = parse_price(conilon_url)

    now = datetime.now()
    trade_date = now.strftime("%d/%m/%Y")

    update_prices(prices_path, price_arabica, price_conilon, trade_date, now)
    update_history(history_path, price_arabica, price_conilon, trade_date, now)
    update_index_html(index_path, price_arabica, price_conilon)


if __name__ == "__main__":
    main()
