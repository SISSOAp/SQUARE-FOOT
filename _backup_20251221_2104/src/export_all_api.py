import time
from src.live_fetch import export_competition_csv

# Códigos que aparecem no seu print do site:
CODES = [
    "WC",
    "CL",
    "BL1",
    "DED",
    "BSA",
    "PD",
    "FL1",
    "ELC",
    "PPL",
    "EC",
    "SA",
    "PL",
]

def main():
    ok = 0
    for code in CODES:
        try:
            # WC costuma não ter dados na free tier dependendo da época, mas não tem problema.
            export_competition_csv(code, status="FINISHED")
            ok += 1
        except Exception as e:
            print(f"[ERRO] {code}: {e}")
        # pausa para não estourar rate limit
        time.sleep(4)

    print(f"Finalizado: {ok}/{len(CODES)} exportados")

if __name__ == "__main__":
    main()
