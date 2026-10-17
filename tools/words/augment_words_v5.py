"""Idempotently extend backend/words.json (v4.0 -> v5.0) with curated Indian merchant, utility,
tax, insurance, charge and UPI-handle coverage. Existing aliases are NEVER overridden: curated
entries use priority 60 and only fill gaps. Run: python tools/words/augment_words_v5.py"""
import json, pathlib, sys

P = pathlib.Path(__file__).resolve().parents[2] / "backend" / "words.json"
d = json.loads(P.read_text(encoding="utf-8"))
ei = d["entity_interpretation"]

# category -> (debit category, credit category, [aliases])
CURATED = {
 "GROCERIES": ("Groceries", "Refund", ["swiggy instamart","instamart","bigbasket","big basket","blinkit","grofers","zepto","dmart","d mart","avenue supermarts","jiomart","jio mart","reliance fresh","reliance smart","more retail","nature basket","spencers","star bazaar","licious","milkbasket","country delight","supr daily","freshtohome","dunzo daily"]),
 "FOOD": ("Food", "Refund", ["dominos","domino's","mcdonald","kfc","burger king","pizza hut","starbucks","barbeque nation","haldiram","chaayos","subway","eatsure","box8","faasos","behrouz","wendys","cafe coffee day","third wave coffee","blue tokri","restaurant","cafe ","bakery","dhaba","biryani"]),
 "SHOPPING": ("Shopping", "Refund", ["purchase subject","mcupos","myntra","ajio","nykaa","tata cliq","lenskart","decathlon","croma","reliance digital","pantaloons","shoppers stop","westside","ikea","firstcry","snapdeal","tatacliq","urban company","pepperfry","bata","max fashion","lifestyle stores","vijay sales","amazon pay","amazon.in","amzn","flipkart","shopsy","meesho"]),
 "TRAVEL": ("Travel", "Refund", ["irctc","redbus","abhibus","indigo","interglobe aviation","spicejet","air india","vistara","akasa air","cleartrip","ixigo","yatra.com","makemytrip","goibibo","easemytrip","oyo","treebo","fabhotels","taj hotels","marriott","airbnb","booking.com","agoda"]),
 "TRANSPORT": ("Transport", "Refund", ["olacabs","ola cabs","ola money","uber","rapido","meru cabs","blusmart","fastag","paytm fastag","nhai","netc","delhi metro","dmrc","bmrc","bmtc","ksrtc","msrtc","tsrtc","upsrtc","gsrtc","parkplus","toll plaza","toll"]),
 "FUEL": ("Fuel", "Refund", ["indian oil","indianoil","iocl","hpcl","hp petrol","bpcl","bharat petroleum","hindustan petroleum","reliance bp","jio-bp","jio bp","nayara","essar oil","shell","petrol pump","filling station","fuel station","filling","fillin","fuels","petro","service station"]),
 "BILLS": ("Bill Payment", "Refund", ["bescom","msedcl","mseb","tneb","tangedco","cesc","bses","tata power","adani electricity","torrent power","mahanagar gas","indraprastha gas","adani gas","reliance jio","jio prepaid","jio postpaid","jiofiber","airtel prepaid","airtel postpaid","airtel xstream","airtel digital","vodafone idea","vi prepaid","vi postpaid","bsnl","mtnl","act fibernet","hathway","excitel","tata play","tata sky","dish tv","sun direct","videocon d2h","d2h","bharat bill","bbps","water board","jal board","municipal corp","gas cylinder","indane","bharatgas","hp gas","recharge","dth"]),
 "SUBSCRIPTIONS": ("Subscription", "Refund", ["netflix","hotstar","disney+","spotify","youtube premium","youtubepremium","google play","googleplay","apple.com","itunes","apple services","prime video","amazon prime","sonyliv","zee5","jiocinema","linkedin","microsoft","adobe","canva","openai","chatgpt","anthropic","notion","dropbox","github","zoom","google one","google cloud","aws","digitalocean","godaddy","hostinger","namecheap"]),
 "ENTERTAINMENT": ("Entertainment", "Refund", ["bookmyshow","book my show","pvr","inox","cinepolis","dream11","mpl","my11circle","paytm insider","wonderla","imagica"]),
 "MEDICAL": ("Medical", "Refund", ["apollo","pharmeasy","1mg","tata 1mg","netmeds","medplus","practo","hospital","clinic","diagnostic","pathlab","path lab","lal path","thyrocare","metropolis","max healthcare","fortis","manipal","medical store","pharmacy","chemist","dental","eye care"]),
 "EDUCATION": ("Education", "Refund", ["byju","unacademy","vedantu","coursera","udemy","upgrad","school fee","college fee","university","tuition","nptel","physics wallah","physicswallah","allen career","aakash"]),
 "FITNESS": ("Fitness", "Refund", ["cult.fit","cultfit","cult fit","gold's gym","golds gym","anytime fitness","gym ","fitness"]),
 "INVESTMENT": ("Investment", "Investment Returns", ["zerodha","groww","upstox","angel one","angel broking","5paisa","icici securities","icicidirect","hdfc securities","kotak securities","motilal oswal","sharekhan","paytm money","kuvera","indian clearing corp","nse clearing","icclltd","bse ltd","nsdl","cdsl","mutual fund","systematic invest","sip ","ppf","nps trust","national pension","smallcase","et money","coin by zerodha"]),
 "TAX": ("Tax Payment", "Refund", ["income tax","incometax","cbdt","tds ","gstn","gst payment","advance tax","tin nsdl","challan","professional tax","property tax","pr tax","e-filing","traces"]),
 "INSURANCE": ("Insurance", "Insurance Claim", ["lic of india","life insurance corp","hdfc life","sbi life","icici prudential","icici lombard","max life","bajaj allianz","star health","care health","niva bupa","tata aia","new india assurance","digit insurance","acko","policybazaar","policy bazaar","reliance general","oriental insurance","united india insurance","national insurance","kotak life","pnb metlife","aditya birla sun life","aviva","insurance premium"]),
}
# fixed-category direction-agnostic items
FIXED = {
 "Bank Charges": ["sms cha","sms chg","sms charge","sms alert","sms chg","amc charge","annual maintenance","atm chg","atm charges","atm fee","min bal","minimum balance","non maintenance","nmab","imps chg","neft chg","rtgs chg","imps charge","neft charge","rtgs charge","gst on","cgst","sgst","igst","chq book","cheque book","debit card fee","debit card annual","locker rent","stamp duty","dd commission","demand draft comm","penal charge","penalty","processing fee","service charge","bank charges","chq return chg","ecs return chg","folio charge","card replacement"],
 "ATM Withdrawal": ["self csh","self cash","csh wdl","cash wdl","self wdl","atm wdl","atm-wdl","atm cash","atm withdrawal","cash wdl","cash withdrawal","nwd-","nwd/","awb/","atw-","atw/"],
 "Interest Income": ["by intt","intt","sbint","credit interest","interest capitalised","interest capitalized","int.pd","int pd","int. pd","interest paid","interest credit","sb int","savings interest","interest cr","int cr","fd interest","rd interest","tdint"],
 "Cashback": ["cashback","cash back","reward points"],
 "Transfer": ["chq dep","cheque dep","by clg","clg cr","clearing","to clg","chq paid","cheque paid","self cheque","by transfer","to transfer","trf to","trf from","fund transfer","own account","sweep","mob bk","mobile banking","net banking","inb/","imb/","dr self","cr self","dr by","cr from","dr to:","cr by:","debit to:","credit by:","money added","money sent","fund added","wallet topup","wallet top up","top up","trf ","trf-","tfr","by trf","to trf","mob/","mmt/","tpt/","clg/","rtgs dr","neft dr","neft cr"],
 "Dividend": ["dividend","div-","divd"],
 "Salary": ["salary","sal for","payroll","wages","stipend"],
 "Business Income": ["cash deposit","csh dep","cemtex dep","cem dep","cash dep","cdm dep","cdm/","by cash","cash-dep"],
 "Loan Payment": ["emi","loan repay","loan instalment","loan installment","nach debit","ecs debit","si debit loan"],
 "Credit Card Payment": ["credit card payment","creditcard payment","cc payment","cardbill","card bill","credit card bill","cc bill","billdesk cc","cred club","cred.club","paid via cred"],
}

import re
# The classifier matches aliases against the NORMALISED narration ("wdl"->"withdrawal", "dep"->"deposit",
# "chq"->"cheque", "cr"->"credit"...), so every curated alias is also registered in its normalised form.
_RULES = []
for _old, _new in d["text_normalization"]["replace_rules"].items():
    _pat = re.compile(r"\b" + re.escape(_old) + r"\b", re.I) if (_old.isalpha() and len(_old) <= 4) else re.compile(re.escape(_old), re.I)
    _RULES.append((_pat, _new))

def _norm(a):
    for _p, _n in _RULES:
        a = _p.sub(_n, a)
    return re.sub(r"\s+", " ", a).strip()

added = 0
def put(group, alias, cfg):
    global added
    g = ei.setdefault(group, {"_description": "Curated Indian coverage (v5.0) - fills gaps, never overrides"})
    for al in dict.fromkeys([alias, _norm(alias)]):
        if not al or any(al in v for k, v in ei.items() if isinstance(v, dict)):
            continue
        g[al] = cfg; added += 1

for grp, (deb, cred, aliases) in CURATED.items():
    for a in aliases:
        a = a.lower()
        put("CURATED_" + grp, a, {
            "credit": {"category": cred, "group": "CURATED", "priority": 60, "confidence": "medium"},
            "debit": {"category": deb, "group": "CURATED", "priority": 60, "confidence": "medium"},
        })
for cat, aliases in FIXED.items():
    for a in aliases:
        a = a.lower()
        put("CURATED_FIXED", a, {"category": cat, "group": "CURATED", "priority": 60, "confidence": "medium"})

# UPI handles (pattern detection list + entity handles)
handles = ["@okaxis","@okhdfc","@okhdfcbank","@okicici","@oksbi","@okbizaxis","@ybl","@ibl","@axl","@pty","@ptys","@pthdfc","@ptsbi","@paytm","@apl","@fbl","@fbpe","@unitype","@mbk","@axisbank","@hdfcbank","@icici","@sbi","@idfcbank","@kotak","@yesbank","@yesbankltd","@upi","@jio","@postbank","@indus","@rbl","@sc","@aubank","@cnrb","@pnb","@boi","@barodampay","@ezetap","@abfspay","@payzapp","@freecharge","@slc","@tapicici","@timecosmos","@waicici","@wahdfcbank","@waaxis","@wasbi","@ikwik","@naviaxis","@jupiteraxis","@superyes","@gocash","@cmsidfc","@lime"]
cur = d["pattern_detection"]["upi_handle"]
for h in handles:
    if h not in cur:
        cur.append(h); added += 1

d["metadata"]["version"] = "5.0"
d["metadata"]["last_updated"] = "2026-10-17"
d["metadata"]["description"] = d["metadata"]["description"].rstrip(".") + ". v5.0 adds CURATED_* Indian merchant/utility/tax/insurance/charge groups and extended UPI handles."
P.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
print("added", added)
