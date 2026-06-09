import subprocess
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
NIFTY_SCRIPT = BASE_DIR / "Nifty_option.py"
CONVERTER_SCRIPT = BASE_DIR / "convert_nifty_json_to_csv.py"
PREPROCESS_SCRIPT = BASE_DIR / "Preprocessing.py"
HTML_SCRIPT = BASE_DIR / "latest_preprocessed_html.py"
DATA_DIR = BASE_DIR / "nifty_data"
CSV_DIR = BASE_DIR / "nifty_data_csv"
START_TIME = dtime(9, 21)
END_TIME = dtime(23, 59)
CHECK_INTERVAL_SECONDS = 10


def now_time() -> dtime:
    return datetime.now().time()


def wait_until_start() -> None:
    current = now_time()
    if current >= END_TIME:
        print(f"Current time {current} is past end time {END_TIME}. Exiting.")
        sys.exit(0)
    if current < START_TIME:
        start_dt = datetime.combine(datetime.today(), START_TIME)
        now_dt = datetime.now()
        wait_seconds = (start_dt - now_dt).total_seconds()
        print(f"Waiting until start time {START_TIME} ({int(wait_seconds)} seconds)")
        time.sleep(max(0, wait_seconds))


def start_scraper() -> subprocess.Popen:
    print("Starting scraper process...")
    return subprocess.Popen([sys.executable, str(NIFTY_SCRIPT)], cwd=BASE_DIR)


def get_processed_json_names() -> set[str]:
    if not CSV_DIR.exists():
        return set()
    return {csv_path.with_suffix(".json").name for csv_path in CSV_DIR.glob("*.csv")}


def process_json_file(json_path: Path) -> None:
    print(f"Processing new JSON: {json_path.name}")
    try:
        subprocess.run([sys.executable, str(CONVERTER_SCRIPT), str(json_path)], cwd=BASE_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Converter failed for {json_path.name}: {exc}")
        return

    csv_path = CSV_DIR / f"{json_path.stem}.csv"
    if not csv_path.exists():
        print(f"Expected CSV not found after conversion: {csv_path}")
        return

    try:
        subprocess.run([sys.executable, str(PREPROCESS_SCRIPT), str(csv_path)], cwd=BASE_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Preprocessing failed for {csv_path.name}: {exc}")
        return

    try:
        subprocess.run([sys.executable, str(HTML_SCRIPT)], cwd=BASE_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"HTML generation failed after preprocessing {csv_path.name}: {exc}")
        return


def run_orchestrator() -> None:
    wait_until_start()
    scraper_process = start_scraper()
    processed = get_processed_json_names()
    print(f"Already processed JSONs: {len(processed)}")

    try:
        while True:
            current = now_time()
            if current >= END_TIME:
                print(f"Reached end time {END_TIME}. Stopping orchestrator.")
                break

            if DATA_DIR.exists():
                json_files = sorted(DATA_DIR.glob("*.json"))
                for json_path in json_files:
                    if json_path.name in processed:
                        continue
                    process_json_file(json_path)
                    processed.add(json_path.name)
            else:
                print(f"Data directory does not exist: {DATA_DIR}")

            time.sleep(CHECK_INTERVAL_SECONDS)
    finally:
        print("Shutting down scraper process...")
        scraper_process.terminate()
        try:
            scraper_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            scraper_process.kill()


if __name__ == "__main__":
    run_orchestrator()
