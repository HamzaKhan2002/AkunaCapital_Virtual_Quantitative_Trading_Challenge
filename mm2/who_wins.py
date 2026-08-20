"""Who wins the tests we never win, vs the tests we do win."""
import re

txt = open(r"mm2\Compiler_Messages_Run_10.txt", encoding="utf-8", errors="ignore").read()
blocks = re.split(r"Test Case (\d+):", txt)[1:]
never = {5, 6, 7, 8, 10, 13, 14, 18, 19}

for title, keep in (("NEVER-WON", lambda t: t in never),
                    ("WE WIN OR PLACE", lambda t: t >= 5 and t not in never)):
    print(f"--- {title} ---")
    for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
        if not keep(tc):
            continue
        rank = re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body)
        print(f"TC{tc:<3} " + " | ".join(f"{n} {v}" for n, v in rank))
    print()
