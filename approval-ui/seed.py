from db import get_conn, init_db

DRAFTS = [
    ("Acme Logistics",
     "Expanding to 3 new warehouses in 2026; hiring a Head of Operations.",
     "Helping Acme Logistics scale warehouse operations",
     "Hi Priya,\n\nCongratulations on the new warehouse expansion. Our platform helps logistics teams cut onboarding time for new sites.\n\nWould you be open to a 15-minute call?\n\nBest,\nSam"),
    ("BrightPath Health",
     "Recently launched a patient-portal app; CEO spoke about reducing no-shows.",
     "Reducing no-shows at BrightPath Health",
     "Hi Dr. Rao,\n\nI read about your new patient portal. We help clinics reduce missed appointments with smart reminders.\n\nCan I share a short case study?\n\nBest,\nSam"),
    ("Cedar Retail",
     "Opened 12 stores this year; investing in inventory forecasting.",
     "Smarter inventory forecasting for Cedar Retail",
     "Hi Marcus,\n\nCedar's growth to 12 stores is impressive. Our forecasting tools help retailers avoid stock-outs.\n\nWorth a quick chat?\n\nBest,\nSam"),
    ("Delta Foods",
     "Announced a partnership with two regional grocery chains.",
     "Supporting Delta Foods' new grocery partnerships",
     "Hi Anita,\n\nCongrats on the new grocery partnerships. We help food suppliers manage multi-retailer order flow.\n\nHappy to share how.\n\nBest,\nSam"),
]


def main():
    init_db()
    conn = get_conn()
    if conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] > 0:
        print("Drafts already exist - skipping seed.")
        return
    with conn:
        conn.executemany(
            """INSERT INTO drafts (run_id, company, research_summary, subject, body)
               VALUES ('run_2026_001', ?, ?, ?, ?)""",
            DRAFTS,
        )
    print(f"Seeded {len(DRAFTS)} drafts with status DRAFT.")
    conn.close()


if __name__ == "__main__":
    main()