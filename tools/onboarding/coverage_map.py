# coverage_map.py — folder -> bank_id classification, aliases, existing coverage.
# Emits .local/folders.json. Bank ids follow the registry json naming.
import os, json, glob

ROOT = r"X:\Airco Projects\Airco Insights fintech\Unified All Statements"
HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))

# folder name -> (bank_id, class). class in {bank, alias, nonbank, loose}
FOLDERS = {
    "APGB Bank": ("apgb", "bank"),
    "APGV Bank": ("apgv", "bank"),
    "AU Small Finance Bank": ("au_sfb", "bank"),
    "Airtel Payments Bank": ("airtel_pb", "bank"),
    "Axis Bank": ("axis", "bank"),
    "Bandhan Bank": ("bandhan", "bank"),
    "Bank of Baroda": ("bank_of_baroda", "bank"),
    "Bank of India": ("bank_of_india", "bank"),
    "Bank of Maharashtra": ("bank_of_maharashtra", "bank"),
    "CSB Bank": ("csb", "bank"),
    "Canara Bank": ("canara", "bank"),
    "Central Bank of India": ("central_bank", "bank"),
    "Citibank": ("citibank", "bank"),
    "City Union Bank": ("city_union", "bank"),
    "Cosmos Bank": ("cosmos", "bank"),
    "DBS Bank": ("dbs", "bank"),
    "DCB Bank": ("dcb", "bank"),
    "Deutsche Bank": ("deutsche", "bank"),
    "Dhanlaxmi Bank": ("dhanlaxmi", "bank"),
    "Equitas Small Finance Bank": ("equitas_sfb", "bank"),
    "Federal Bank": ("federal", "bank"),
    "Fincare SFB Bank": ("fincare_sfb", "bank"),
    "Fino Payments Bank": ("fino_pb", "bank"),
    "HDFC Bank": ("hdfc", "bank"),
    "HSBC": ("hsbc", "bank"),
    "ICICI Bank": ("icici", "bank"),
    "IDBI Bank": ("idbi", "bank"),
    "IDFC First Bank": ("idfc", "bank"),
    "India Post Payments Bank": ("ippb", "bank"),
    "Indian Bank": ("indian_bank", "bank"),
    "Indian Overseas Bank": ("iob", "bank"),
    "IndusInd Bank": ("indusind", "bank"),
    "Karnataka Bank": ("karnataka", "bank"),
    "Karur Vysya Bank": ("kvb", "bank"),
    "Kotak Bank": ("kotak", "alias"),           # alias of kotak
    "Kotak Mahindra Bank": ("kotak", "bank"),
    "Paytm Bank": ("paytm", "alias"),            # alias of paytm
    "Paytm Payments Bank": ("paytm", "bank"),
    "Punjab National Bank": ("pnb", "bank"),
    "RBL Bank": ("rbl", "bank"),
    "SBI": ("sbi", "bank"),
    "SBM Bank": ("sbm", "bank"),
    "South Indian Bank": ("south_indian", "bank"),
    "Standard Chartered Bank": ("standard_chartered", "bank"),
    "Tamilnad Mercantile Bank": ("tmb", "bank"),
    "UCO Bank": ("uco", "bank"),
    "Ujjivan Small Finance Bank": ("ujjivan_sfb", "bank"),
    "Union Bank of India": ("union", "bank"),
    "Yes Bank": ("yes", "bank"),
    "Human Verification": (None, "nonbank"),
    "Non_Bank_Documents": (None, "nonbank"),
    "Other_Unknown": (None, "nonbank"),
    "Others": (None, "nonbank"),
    "Unknown": (None, "nonbank"),
}

# folder bank_id -> extractor package name where they differ
EXT_ALIAS = {"bank_of_baroda": "bob", "bank_of_maharashtra": "bom",
             "equitas_sfb": "equitas", "standard_chartered": "scb",
             "ujjivan_sfb": "ujjivan"}

def main():
    reg_banks = {os.path.basename(p)[:-5] for p in
                 glob.glob(os.path.join(BACKEND, "app/services/statement_engine/banks/*.json"))}
    reg_banks.discard("_masks")
    extractor_pkgs = {d for d in os.listdir(os.path.join(BACKEND, "app/services/statement_engine/extractors"))
                      if os.path.isdir(os.path.join(BACKEND, "app/services/statement_engine/extractors", d))}
    legacy_procs = {"hdfc","axis","icici","bank_of_india","indian_bank","kotak","sbi","canara",
                    "idfc","karnataka","paytm","union","bank_of_baroda","unknown"}
    out = {}
    for folder, (bid, cls) in FOLDERS.items():
        ext = EXT_ALIAS.get(bid, bid)
        out[folder] = {
            "bank_id": bid, "class": cls,
            "registry_json": bid in reg_banks if bid else False,
            "extractor_pkg": ext in extractor_pkgs if bid else False,
            "legacy_processor": bid in legacy_procs if bid else False,
            "layoutspec": os.path.exists(os.path.join(BACKEND, f"app/services/statement_engine/extractors/{ext}/layout_spec.py")) if bid else False,
        }
    json.dump(out, open(os.path.join(LOCAL, "folders.json"), "w"), indent=1)
    print(json.dumps(out, indent=0)[:800])

if __name__ == "__main__":
    main()
