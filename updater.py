import json,re,datetime,requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import quote
UTC=datetime.timezone.utc
NOW=datetime.datetime.now(UTC).isoformat(timespec="minutes")
HEAD={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
P=Path("data.json")
try: data=json.loads(P.read_text())
except: data={}
data.setdefault("items",{})
def get(url):
 r=requests.get(url,headers=HEAD,timeout=22);r.raise_for_status()
 return BeautifulSoup(r.text,"html.parser")
def gbp(s):
 m=re.search(r"£\s*([\d,]+(?:\.\d{1,2})?)",s)
 return float(m.group(1).replace(",","")) if m else None
def update_new(key,price,url,description):
 if not price or not 20<price<2500:return
 data["items"].setdefault(key,{})["new"]={"price":price,"url":url,"description":description,"checked":NOW}
# Retail price observations: only scrape a named product from a known source.
sources=[
 ("mobo","https://www.maxmybuild.com/uk/motherboards/msi-b850-gaming-plus-wifi6e","B850 GAMING PLUS WIFI6E"),
 ("ram","https://theramageddon.com/uk-en/ddr5-6000-cl30-ram/","KLEVV Cras V RGB 32 GB"),
 ("gpu","https://pctechvault.com/market-watch/geforce-rtx-5070-ti/?component=gpu&market=new-retail&region=UK","GeForce RTX 5070 Ti (any brand)"),
 ("case","https://www.watercoolinguk.co.uk/product/montech-king-95-pro-midi-tower-tempered-glass-argb-white/","Montech KING 95 PRO White")
]
errors=[]
for key,url,desc in sources:
 try:
  soup=get(url); txt=soup.get_text(" ",strip=True)
  price=None
  if key=="mobo":
   m=re.search(r"Where to buy the B850 GAMING PLUS WIFI6E.{0,900}?£\s*([\d,.]+)",txt,re.I)
   if m:price=gbp("£"+m.group(1))
  elif key=="ram":
   m=re.search(r"KLEVV Cras V RGB 32 GB \(2 x 16 GB\).*?£\s*([\d,.]+)",txt,re.I)
   if m:price=gbp("£"+m.group(1))
  elif key=="gpu":
   m=re.search(r"Cheapest in stock now.{0,550}?£\s*([\d,.]+)",txt,re.I)
   if m:price=gbp("£"+m.group(1))
  elif key=="case":
   # Only price near explicit stock/product section
   m=re.search(r"(?:Available|in stock).{0,450}?£\s*([\d,.]+)",txt,re.I)
   if m:price=gbp("£"+m.group(1))
  if price:update_new(key,price,url,desc)
  else:errors.append(key+": retail price not parsed")
 except Exception as e: errors.append(key+": "+str(e)[:90])
# eBay auction results, when the public search endpoint returns parsable listings.
queries={
 "mobo":"MSI B850 Gaming Plus WiFi6E",
 "ram":"32GB DDR5 6000 CL30 RGB",
 "gpu":"RTX 5070 Ti 16GB",
 "case":"Montech KING 95 PRO white"
}
def valid(key,title):
 t=title.lower()
 if any(x in t for x in ["box only","empty box","faulty","for parts","read description","waterblock","backplate","broken","wanted","rtx 5070 ti super"]):return False
 return {"mobo":lambda: "b850" in t and "gaming plus" in t and ("wifi6e" in t or "wifi 6e" in t),
 "ram":lambda:("32gb" in t or "2x16" in t or "2 x 16" in t) and "6000" in t and ("cl30" in t or "c30" in t) and "rgb" in t,
 "gpu":lambda:"5070 ti" in t and "16gb" in t,
 "case":lambda:"king 95" in t and "pro" in t and ("white" in t or "wht" in t)}[key]()
for key,q in queries.items():
 url="https://www.ebay.co.uk/sch/i.html?_nkw="+quote(q)+"&LH_Auction=1&LH_PrefLoc=1&_sop=1"
 data["items"].setdefault(key,{})["auction_search"]=url
 try:
  soup=get(url)
  results=[]
  for el in soup.select("li.s-item, div.s-card")[:65]:
   titleel=el.select_one(".s-item__title, .s-card__title")
   priceel=el.select_one(".s-item__price, .s-card__price")
   linkel=el.select_one("a.s-item__link, a.s-card__link")
   if not titleel or not priceel or not linkel:continue
   title=titleel.get_text(" ",strip=True)
   if not valid(key,title):continue
   raw=priceel.get_text(" ",strip=True)
   price=gbp(raw)
   if price is None or " to " in raw:continue
   shipel=el.select_one(".s-item__shipping, .s-item__logisticsCost, .s-card__shipping")
   shiptxt=shipel.get_text(" ",strip=True) if shipel else ""
   ship=0 if "free" in shiptxt.lower() else gbp(shiptxt)
   if ship is None:continue # don't pretend shipping is free
   href=linkel.get("href","")
   if not href.startswith("http") or "ebay.co.uk" not in href:continue
   more=el.get_text(" ",strip=True)
   if not re.search(r"\bbid(s)?\b",more,re.I):continue # exclude fixed price
   # Only surface a strong discount against a recorded verified-new comparator.
   ref=data["items"][key].get("new",{})
   if not ref.get("price") or price+ship>ref["price"]*.85:continue
   results.append({"title":title[:120],"price":price,"shipping":ship,"url":href.split("?")[0],"detail":more[-240:],"checked":NOW,"saving":round(ref["price"]-price-ship,2)})
  results.sort(key=lambda x:x["price"]+x["shipping"])
  data["items"][key]["deals"]=results[:3]
  data["items"][key]["auction_checked"]=NOW
 except Exception as e:
  errors.append(key+": eBay "+str(e)[:70])
  # Do not keep expired/unverified auction offers after a failed fetch
  data["items"][key]["deals"]=[]
data["attempted_at"]=NOW
data["errors"]=errors
P.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
print("Checked:",NOW,"errors:",errors)
