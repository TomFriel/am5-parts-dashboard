"""Best-effort public UK parts discovery. No paid services or secrets required.
Sources: named product pages, price aggregators, Bing RSS discovery and eBay public search.
Missing fields stay unknown. Price/stock are never invented.
"""
import datetime as dt, json, re, time, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
import requests
from bs4 import BeautifulSoup

NOW=dt.datetime.now(dt.timezone.utc)
STAMP=NOW.isoformat(timespec="minutes")
P=Path("data.json")
try: old=json.loads(P.read_text())
except: old={}
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; AM5PriceResearch/1.0; +https://github.com/TomFriel/am5-parts-dashboard)","Accept-Language":"en-GB,en;q=.9"})
PARTS={
 "mobo":{"q":'"MSI B850 GAMING PLUS WIFI6E" buy UK', "terms":["b850","gaming plus","wifi6e"]},
 "ram":{"q":'"32GB" "DDR5" "6000" "CL30" "RGB" EXPO UK buy', "terms":["ddr5","6000","rgb"]},
 "gpu":{"q":'"RTX 5070 Ti" "16GB" buy UK', "terms":["5070","ti","16gb"]},
 "case":{"q":'"Montech KING 95 PRO" "White" UK buy', "terms":["king","95","pro","white"]}
}
RETAILERS={
 "scan.co.uk":"Scan","cclonline.com":"CCL","overclockers.co.uk":"Overclockers",
 "awd-it.co.uk":"AWD-IT","ebuyer.com":"Ebuyer","currys.co.uk":"Currys",
 "box.co.uk":"Box","novatech.co.uk":"Novatech","laptopsdirect.co.uk":"Laptops Direct",
 "watercoolinguk.co.uk":"Watercooling UK","amazon.co.uk":"Amazon UK",
 "uk-store.msi.com":"MSI UK","computerorbit.com":"Computer Orbit",
 "theitbay.com":"The IT Bay","morecoco.co.uk":"MoreCoCo",
 "idealo.co.uk":"idealo","pricespy.co.uk":"PriceSpy"}
# Known exact-model URLs. Discovery adds links where available.
SEEDS={
 "mobo":[
 "https://www.cclonline.com/b850-gaming-plus-wifi6e-msi-b850-gaming-plus-wifi6e-atx-motherboard-for-amd-am5-cpus/",
 "https://www.scan.co.uk/products/msi-b850-gaming-plus-wifi6e-amd-b850-am5-ddr5-pcie-40-2x-m2-25g-wifi6e-usb-32-aplusc-amd-expo-atx",
 "https://uk-store.msi.com/products/b850-gaming-plus-wifi6e"],
 "ram":[],
 "gpu":[],
 "case":[
 "https://www.scan.co.uk/products/montech-king-95-pro-white-mid-tower-chassis-argb-lighting-2x-140mm-fans-4x-120mm-mitx-matx-atx",
 "https://www.watercoolinguk.co.uk/product/montech-king-95-pro-midi-tower-tempered-glass-argb-white/",
 "https://www.idealo.co.uk/compare/203673893/montech-king-95-pro-white.html",
 "https://pricespy.co.uk/product.php?p=12992220"]
}
def money(s):
 m=re.search(r"£\s*([\d,]+(?:\.\d\d?)?)",str(s))
 return round(float(m.group(1).replace(",","")),2) if m else None
def get(url):
 r=S.get(url,timeout=18);r.raise_for_status()
 if "text/html" not in r.headers.get("Content-Type","text/html"):raise ValueError("Not HTML")
 return BeautifulSoup(r.text[:2500000],"html.parser")
def domain(url):
 return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
def host_ok(url):
 host=domain(url)
 return host in RETAILERS
def matching(key,txt):
 s=re.sub(r"[\s_-]+"," ",str(txt).lower())
 if key=="mobo":return "b850" in s and "gaming plus" in s and ("wifi6e" in s or "wifi 6e" in s)
 if key=="ram":
  return ("32gb" in s or "32 gb" in s or "2x16" in s or "2 x 16" in s) and "6000" in s and ("cl30" in s or "c30" in s or "cl 30" in s) and "rgb" in s and ("ddr5" in s or "ddr 5" in s)
 if key=="gpu":return "5070 ti" in s and ("16gb" in s or "16 gb" in s) and not any(x in s for x in ["water block","waterblock","backplate","box only"])
 if key=="case":return "king 95" in s and "pro" in s and "white" in s
def disqualified(txt):
 t=txt.lower()
 return any(x in t for x in ["pre order","pre-order","preorder","out of stock","sold out","currently unavailable","unavailable","item overdue","email me when","notify me when","not available to buy","discontinued"])
def jsonld(soup):
 for tag in soup.select('script[type="application/ld+json"]'):
  try:
   root=json.loads(tag.string or tag.get_text())
   stack=[root]
   while stack:
    obj=stack.pop()
    if isinstance(obj,list):stack.extend(obj)
    elif isinstance(obj,dict):
     if isinstance(obj.get("@graph"),list):stack+=obj["@graph"]
     if obj.get("@type") in ("Product","IndividualProduct") or ("Product" in obj.get("@type",[]) if isinstance(obj.get("@type"),list) else False):
      yield obj
  except Exception:continue
def numeric(x):
 try:
  v=float(str(x).replace(",","").replace("£",""))
  return round(v,2) if 20<v<4000 else None
 except:return None
def retail(key,url):
 soup=get(url); name=RETAILERS[domain(url)]
 title=(soup.title.get_text(" ",strip=True) if soup.title else "")[:170]
 text=soup.get_text(" ",strip=True)[:45000]
 if not matching(key,title):return None
 if re.search(r"\b(?:B[ -]?GRADE|REFURBISHED|USED|OPEN BOX)\b",title,re.I):return None
 if domain(url) in ("idealo.co.uk","pricespy.co.uk"):
  # Comparison services are discovery sources; not individual merchant checkout offers
  return None
 # Product-page availability: avoid rejecting pages just because they include
 # a generic "Email me when availability changes" notification button.
 intro=text[:2200].lower()
 if name=="Scan":
  if "pre order" in intro or "pre-order" in intro or "item overdue" in intro:return None
  if "add to basket" not in intro and "in stock" not in intro:return None
 elif name=="MSI UK":
  if "unavailable" in intro or "sold out" in intro:return None
 else:
  if any(z in intro for z in ("out of stock","sold out","currently unavailable","pre order","pre-order","preorder")):return None
 price=None
 for product in jsonld(soup):
  if not matching(key,product.get("name",title)):continue
  offers=product.get("offers",[])
  if isinstance(offers,dict):offers=[offers]
  for o in offers:
   if not isinstance(o,dict):continue
   avail=str(o.get("availability","")).lower()
   if "outofstock" in avail or "preorder" in avail or "soldout" in avail:continue
   price=numeric(o.get("price") or o.get("lowPrice"))
   if price:break
  if price:break
 if price is None:
  for sel in ['meta[property="product:price:amount"]','meta[property="og:price:amount"]','meta[itemprop="price"]','[itemprop="price"]']:
   node=soup.select_one(sel)
   if node:
    price=numeric(node.get("content") or node.get("value") or node.get_text(" ",strip=True))
    if price:break
 if name=="Scan":
  # Scan renders 'RRP: £124.99£109.98'; the second is the offer price.
  m=re.search(r"RRP:\s*£[\d,.]+\s*£([\d,.]+)",text[:4000],re.I)
  if m:price=numeric(m.group(1))
 if price is None:
  # Scan and CCL product pages: first pound amount on exact model product block.
  if name in ("Scan","CCL","Watercooling UK","MSI UK"):
   price=money(text[:4200])
 if not price:return None
 if key=="case" and price>150:return None
 postage=None
 m=re.search(r"£\s*([\d.]+)\s+(?:next day )?delivery",text[:7000],re.I)
 if m:postage=numeric(m.group(1)) or float(m.group(1))
 if re.search(r"free delivery on this item",text[:6500],re.I):postage=0.0
 return {"kind":"new","name":title,"retailer":name,"price":price,"postage":postage,"url":url,"checked":STAMP,"stock":"product page checked","source":"retailer","confidence":"site parsed"}
def discovery(key):
 urls=list(SEEDS[key])
 q=PARTS[key]["q"]
 for query in (q,q+" site:scan.co.uk OR site:cclonline.com OR site:overclockers.co.uk OR site:awd-it.co.uk",q+" site:ebuyer.com OR site:box.co.uk OR site:novatech.co.uk"):
  try:
   rss=S.get("https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query),timeout=12)
   rss.raise_for_status()
   root=ET.fromstring(rss.content)
   for link in root.findall(".//item/link"):
    u=(link.text or "").strip()
    if host_ok(u) and u not in urls:urls.append(u)
  except Exception:continue
 return urls[:28]
def auctions(key,errors):
 # Public eBay pages are frequently blocked; never invent current bid or end time.
 query={"mobo":"MSI B850 Gaming Plus WiFi6E","ram":"32GB DDR5 6000 CL30 RGB","gpu":"RTX 5070 Ti 16GB","case":"Montech KING 95 PRO White"}[key]
 search="https://www.ebay.co.uk/sch/i.html?_nkw="+urllib.parse.quote_plus(query)+"&LH_Auction=1&LH_PrefLoc=1&_sop=1"
 found=[]
 try:
  soup=get(search)
  for el in soup.select("li.s-item, div.s-card")[:90]:
   title_el=el.select_one(".s-item__title,.s-card__title")
   cost_el=el.select_one(".s-item__price,.s-card__price")
   link_el=el.select_one("a.s-item__link,a.s-card__link")
   if not(title_el and cost_el and link_el):continue
   title=title_el.get_text(" ",strip=True)
   if not matching(key,title) or any(z in title.lower() for z in ["faulty","spares","repair","box only","read description"]):continue
   full=el.get_text(" ",strip=True)
   if not re.search(r"\bbids?\b",full,re.I):continue
   p=money(cost_el.get_text(" ",strip=True))
   if not p:continue
   ship=el.select_one(".s-item__shipping,.s-item__logisticsCost,.s-card__shipping")
   ship_text=ship.get_text(" ",strip=True) if ship else ""
   post=0.0 if "free" in ship_text.lower() else money(ship_text)
   end=el.select_one(".s-item__time-left,.s-item__timeLeft")
   end_text=end.get_text(" ",strip=True) if end else None
   url=link_el.get("href","").split("?")[0]
   if not url.startswith("https://") or "ebay." not in domain(url):continue
   found.append({"kind":"auction","name":title,"retailer":"eBay","price":p,"postage":post,"url":url,"checked":STAMP,"ends":end_text,"stock":"auction listed","source":"eBay results","confidence":"search card parsed"})
 except Exception as e:errors.append("eBay "+key+": "+str(e)[:70])
 return found[:12],search
def run():
 results={"attempted_at":STAMP,"items":{},"errors":[],"about":"Public retail and auction research; coverage incomplete. Missing postage means not yet comparable."}
 for key in PARTS:
  item={"offers":[],"auction_search":"","scan_count":0,"problems":[]}
  urls=discovery(key)
  for u in urls:
   if not host_ok(u):continue
   try:
    offer=retail(key,u)
    if offer:item["offers"].append(offer)
   except Exception as e:item["problems"].append(domain(u)+": "+str(e)[:55])
  aa,item["auction_search"]=auctions(key,item["problems"])
  item["offers"]+=aa
  seen=set()
  dedup=[]
  for offer in sorted(item["offers"],key=lambda o:o["price"]+(o["postage"] or 0)):
   token=offer["url"].split("?")[0].rstrip("/")
   if token not in seen:dedup.append(offer);seen.add(token)
  item["offers"]=dedup[:30]
  item["scan_count"]=len(urls)
  results["items"][key]=item
  print(key,"urls",len(urls),"offers",len(dedup),"errors",len(item["problems"]))
 P.write_text(json.dumps(results,indent=2,ensure_ascii=False)+"\n")
if __name__=="__main__":run()
