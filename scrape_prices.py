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
    """
    Write the latest coffee prices into ``prices.json`` in a structure
    compatible with the front‑end data loader.

    The output JSON contains meta‑information about the update time
    (``ultima_atualizacao``), a human‑readable date and time, and a
    nested ``cafe`` object with pricing details for each type.  The
    structure mirrors the fallback data used by ``data-loader.js`` on
    cotacaodocafe.com so that the site can parse the values directly
    from this file.

    Example output::

        {
            "ultima_atualizacao": "2025-09-19T18:20:18.890339",
            "data_formatada": "19/09/2025",
            "hora_formatada": "18:20:18",
            "pregao_aberto": true,
            "fonte": "Notícias Agrícolas",
            "cafe": {
                "arabica": { "preco": 2292.66, "unidade": "saca", "peso_kg": 60, "moeda": "BRL" },
                "robusta": { "preco": 1402.21, "unidade": "saca", "peso_kg": 60, "moeda": "BRL" }
            }
        }

    ``data_formatada`` and ``hora_formatada`` are provided for
    convenience so the front‑end can display localized date/time
    without additional parsing.
    """
    # Build base meta information
    data = {
        "ultima_atualizacao": now.isoformat(),
        "data_formatada": now.strftime("%d/%m/%Y"),
        "hora_formatada": now.strftime("%H:%M:%S"),
        "pregao_aberto": is_market_open(),
        "fonte": "Notícias Agrícolas",
    }
    # Build nested price objects for arabica and robusta/conilon
    arabica_obj = {
        "preco": price_arabica,
        "unidade": "saca",
        "peso_kg": 60,
        "moeda": "BRL",
    }
    robusta_obj = {
        "preco": price_conilon,
        "unidade": "saca",
        "peso_kg": 60,
        "moeda": "BRL",
    }
    data["cafe"] = {
        "arabica": arabica_obj,
        # Use "robusta" as canonical key (data-loader.js validates this)
        "robusta": robusta_obj,
        # Provide "conilon" alias for backwards compatibility
        "conilon": robusta_obj,
    }
    prices_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def update_history(
    history_path: Path,
    price_arabica: float,
    price_conilon: float,
    trade_date: str,
    now: datetime,
) -> None:
    """
    Append the latest coffee prices to the historical JSON file in a format
    used by the site.

    The history file stores **two** records per update: one for arábica and
    one for conilon/robusta.  Each record includes the date to which the
    price refers (``referente_a``), the exact timestamp when the data was
    collected (``coletado_em``), and identifies the product and type along
    with its value.  Only the most recent 20 records (10 updates) are
    retained.
    """
    history: List[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
        except json.JSONDecodeError:
            history = []
    # Build entry for arabica
    entry_arabica = {
        "referente_a": trade_date,
        "coletado_em": now.isoformat(),
        "produto": "cafe",
        "tipo": "arabica",
        "valor": price_arabica,
        "unidade": "saca",
        "moeda": "BRL",
    }
    # Build entry for conilon/robusta (use "conillon" spelling expected by the site)
    entry_conillon = {
        "referente_a": trade_date,
        "coletado_em": now.isoformat(),
        "produto": "cafe",
        "tipo": "conillon",
        "valor": price_conilon,
        "unidade": "saca",
        "moeda": "BRL",
    }
    history.append(entry_arabica)
    history.append(entry_conillon)
    # Keep the last 20 entries (10 updates)
    history = history[-20:]
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
