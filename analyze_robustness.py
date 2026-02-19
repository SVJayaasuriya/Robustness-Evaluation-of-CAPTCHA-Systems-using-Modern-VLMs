import pandas as pd
import os

def analyze_results(csv_file="test_results.csv"):
    if not os.path.exists(csv_file):
        print("No test_results.csv file found. Run your CAPTCHA solver first.")
        return

    df = pd.read_csv(csv_file)

    # Only keep rows with essential fields
    needed_cols = ["captcha_type", "status", "time_taken"]
    for col in needed_cols:
        if col not in df.columns:
            print(f"Column '{col}' missing in CSV. Cannot analyze.")
            return

    df = df.dropna(subset=needed_cols)

    # Normalize status values to lower-case for safety
    df["status"] = df["status"].str.lower().str.strip()

    total_tests = len(df)
    total_success = (df["status"] == "success").sum()
    total_fail = (df["status"] == "fail").sum()
    total_error = (df["status"] == "error").sum()

    success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0.0
    avg_time_global = df["time_taken"].mean() if total_tests > 0 else 0.0

    print("\n====== Overall Robustness Report ======")
    print(f"Total Tests Run        : {total_tests}")
    print(f"Successful Solves      : {total_success}")
    print(f"Failed Attempts        : {total_fail}")
    print(f"Errors / Exceptions   : {total_error}")
    print(f"Overall Success Rate   : {success_rate:.2f}%")

    print("\n====== Breakdown by CAPTCHA Type ======")

    # If attempts column exists, use it; otherwise fallback
    has_attempts = "attempts" in df.columns
    if not has_attempts:
        df["attempts"] = 1

    # Per-type aggregates
    grouped = df.groupby("captcha_type")

    per_type = grouped.agg(
        tests=("captcha_type", "count"),
        successes=("status", lambda x: (x == "success").sum()),
        fails=("status", lambda x: (x == "fail").sum()),
        errors=("status", lambda x: (x == "error").sum()),
        avg_time_all=("time_taken", "mean"),
        avg_attempts=("attempts", "mean")
    )

    # Success rate per type
    per_type["success_rate_%"] = per_type["successes"] / per_type["tests"] * 100

    # For robustness, we want “harder = higher score”
    # We'll combine:
    #  - lower success rate  -> higher difficulty
    #  - higher avg time     -> higher difficulty
    #
    # Simple robustness score (0–100):
    #   difficulty_factor = (1 - success_rate_norm)*0.7 + time_factor*0.3
    # where:
    #   success_rate_norm = success_rate / 100
    #   time_factor = avg_time_all / global_avg_time (clipped)
    #
    # If global avg_time is 0 (edge case), skip time factor.

    if avg_time_global > 0:
        time_factor = (per_type["avg_time_all"] / avg_time_global).clip(lower=0.0, upper=3.0)
    else:
        time_factor = 1.0  # neutral factor if no timing data

    success_rate_norm = (per_type["success_rate_%"] / 100.0).clip(lower=0.0, upper=1.0)
    difficulty = (1.0 - success_rate_norm) * 0.7 + time_factor * 0.3

    per_type["robustness_score_0_100"] = (difficulty * 100).clip(lower=0.0, upper=100.0)

    # Round some columns for nicer printing
    per_type["avg_time_all"] = per_type["avg_time_all"].round(3)
    per_type["success_rate_%"] = per_type["success_rate_%"].round(2)
    per_type["robustness_score_0_100"] = per_type["robustness_score_0_100"].round(2)

    print(per_type[[
        "tests",
        "successes",
        "fails",
        "errors",
        "success_rate_%",
        "avg_time_all",
        "robustness_score_0_100"
    ]])

    # Save detailed CSV
    per_type.to_csv("robustness_report_by_type.csv")
    print("\nSaved detailed report as: robustness_report_by_type.csv")
    print("   Columns include: tests, successes, fails, errors, success_rate, avg_time, avg_attempts, robustness_score")

if __name__ == "__main__":
    analyze_results()
