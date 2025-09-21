"""
Produces a large dishes dataset (India + world). Usage:
  python build_dishes_dataset.py --out meals_100k.sqlite --max-items 100000 --threads 12

Requirements:
  pip install requests rdflib SPARQLWrapper beautifulsoup4 lxml aiohttp aiosqlite tqdm python-slugify
(You may add edamam USDA clients if you use them.)
"""

import argparse
import asyncio
import aiohttp
import aiosqlite
import csv
import json
import math
import os
import re
import time
from bs4 import BeautifulSoup
from SPARQLWrapper import SPARQLWrapper, JSON
from slugify import slugify
from tqdm import tqdm

WIKIPEDIA_BASE = "https://en.wikipedia.org"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# ----------------------
# Utilities
# ----------------------
def safe_filename(s):
    return slugify(s)[:200]

def normalize_name(name):
    return re.sub(r'\s+', ' ', name).strip().lower()

# ----------------------
# Step 1: Harvest dish names (Wikipedia lists + Wikidata)
# ----------------------
WIKIPEDIA_START_PAGES = [
    "https://en.wikipedia.org/wiki/List_of_Indian_dishes",
    "https://en.wikipedia.org/wiki/List_of_Indian_sweets_and_desserts",
    "https://en.wikipedia.org/wiki/Category:Indian_cuisine",
    "https://en.wikipedia.org/wiki/List_of_cuisines",
    "https://en.wikipedia.org/wiki/List_of_dishes_by_country"
]

def harvest_from_wikipedia_pages():
    import requests
    names = set()
    for url in WIKIPEDIA_START_PAGES:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent":"MealsBuilder/1.0 (contact: you@example.com)"})
            soup = BeautifulSoup(resp.text, "lxml")
            # find lists and links
            for a in soup.select("a"):
                href = a.get("href") or ""
                text = (a.get_text() or "").strip()
                if "/wiki/" in href and ':' not in href and len(text)>1:
                    # filter out disambiguation/template pages quick heuristics
                    if any(x in text.lower() for x in ["list of", "category:", "template"]): 
                        continue
                    names.add((text, WIKIPEDIA_BASE + href))
        except Exception as e:
            print("wiki harvest error", url, e)
    return list(names)

def harvest_from_wikidata(limit=200000):
    # Query Wikidata for items instance of recipe/food/dish and having country ( India or global)
    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    # This SPARQL query fetches items classified as food/dish and their labels; it will return many items.
    query = """
    SELECT ?item ?itemLabel ?countryLabel WHERE {
      ?item wdt:P31/wdt:P279* wd:Q2095.  # instance of 'dish' or subclass (Q2095 = dish)
      OPTIONAL { ?item wdt:P495 ?country. } # country of origin
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } LIMIT %d
    """ % limit
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    out = []
    for r in results["results"]["bindings"]:
        label = r["itemLabel"]["value"]
        qid = r["item"]["value"].split("/")[-1]
        country = r.get("countryLabel", {}).get("value", "")
        out.append((label, "https://www.wikidata.org/wiki/" + qid, qid, country))
    return out

# ----------------------
# Step 2: For each dish get Wikipedia page & extract ingredients
# ----------------------
async def fetch_html(session, url):
    try:
        async with session.get(url, timeout=20, headers={"User-Agent":"MealsBuilder/1.0"}) as r:
            if r.status == 200:
                return await r.text()
    except Exception as e:
        return None
    return None

def extract_ingredients_from_wiki_html(html):
    # heuristics: find 'Ingredients' section or list items near 'Ingredients' header
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    # try infobox first (may contain main ingredients)
    ingredients = []
    # look for ul in sections with 'ingredient' in heading
    for header in soup.find_all(['h2','h3','h4']):
        htext = header.get_text().lower()
        if 'ingredient' in htext:
            # next sibling lists
            sib = header.find_next_sibling()
            if sib:
                for li in sib.find_all('li'):
                    ingredients.append(li.get_text().strip())
            if ingredients:
                break
    # fallback: search for lists in the page that look like ingredient lists
    if not ingredients:
        for ul in soup.select("ul"):
            txt = " ".join(li.get_text() for li in ul.find_all("li"))
            if len(txt)>0 and any(k in txt.lower() for k in ["cup","tbsp","tsp","gram","g","kg","cup","slice","pinch"]):
                for li in ul.find_all("li"):
                    ingredients.append(li.get_text().strip())
                if ingredients:
                    break
    # dedupe and clean
    cleaned = []
    for ing in ingredients:
        ing = re.sub(r'\([^)]*\)', '', ing)  # remove parenthesis
        ing = re.sub(r'\[[^\]]*\]', '', ing)
        ing = ing.strip()
        if ing and ing.lower() not in [c.lower() for c in cleaned]:
            cleaned.append(ing)
    return cleaned

# ----------------------
# Step 3: Map ingredients to nutrition (example: via Edamam / USDA)
# ----------------------
# Example placeholder functions: you must configure USDA or Edamam API keys
EDAMAM_BASE = "https://api.edamam.com/api/food-database/v2/parser"
def lookup_ingredient_edamam(ingredient_text, app_id, app_key):
    # simple sync call (used for demonstration)
    import requests, urllib
    params = {"app_id": app_id, "app_key": app_key, "ingr": ingredient_text}
    r = requests.get(EDAMAM_BASE, params=params, timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

# ----------------------
# Step 4: Orchestrate async harvest + db save
# ----------------------
async def worker(queue, session, db, args, edamam_cfg):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
        name, urlinfo = item[0], item[1]
        try:
            html = None
            if urlinfo:
                html = await fetch_html(session, urlinfo)
            ingredients = extract_ingredients_from_wiki_html(html) if html else []
            # minimal nutrition estimate (placeholder): calories/protein etc computed if edamam provided
            n = {"calories_kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None}
            # Save
            await db.execute("""
                INSERT INTO dishes(name, normalized_name, source_url, ingredients_json, calories_kcal, protein_g, carbs_g, fat_g)
                VALUES (?,?,?,?,?,?,?,?)
            """, (name, normalize_name(name), urlinfo or "", json.dumps(ingredients), n["calories_kcal"], n["protein_g"], n["carbs_g"], n["fat_g"]))
            await db.commit()
        except Exception as e:
            print("worker error", name, e)
        queue.task_done()

async def main_async(out_db, max_items=100000, threads=12):
    # Stage A: harvest from wikipedia & wikidata
    wiki_names = harvest_from_wikipedia_pages()
    print("Wikipedia seed names:", len(wiki_names))
    wikidata_items = harvest_from_wikidata(limit=max_items)
    print("Wikidata items:", len(wikidata_items))
    # combine (prioritize wikidata items with QID)
    combined = []
    for label, url in wiki_names:
        combined.append((label, url))
    for label, url, qid, country in wikidata_items:
        combined.append((label, "https://www.wikidata.org/wiki/" + qid))
    # dedupe by normalized name
    seen = set()
    roster = []
    for name, url in combined:
        nn = normalize_name(name)
        if nn in seen: continue
        seen.add(nn)
        roster.append((name, url))
        if len(roster) >= max_items:
            break
    print("Total roster:", len(roster))
    # Setup DB
    db = await aiosqlite.connect(out_db)
    await db.execute("""
      CREATE TABLE IF NOT EXISTS dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        normalized_name TEXT,
        source_url TEXT,
        ingredients_json TEXT,
        calories_kcal REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL
      )
    """)
    await db.commit()
    # Async workers
    queue = asyncio.Queue()
    for item in roster:
        queue.put_nowait(item)
    for _ in range(threads):
        queue.put_nowait(None)  # sentinel for each worker
    async with aiohttp.ClientSession() as session:
        workers = [asyncio.create_task(worker(queue, session, db, None, None)) for _ in range(threads)]
        await queue.join()
        for w in workers:
            w.cancel()
    await db.close()
    print("Done; DB:", out_db)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="meals_dataset.sqlite")
    parser.add_argument("--max-items", type=int, default=100000)
    parser.add_argument("--threads", type=int, default=12)
    args = parser.parse_args()
    asyncio.run(main_async(args.out, args.max_items, args.threads))

if __name__ == "__main__":
    main()
