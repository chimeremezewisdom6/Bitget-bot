import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("scanner")

def main():
    log.info("====================================================================================================")
    log.info("🛑 AUTOMATED TRADING & SCANNING HAS BEEN COMPLETELY DISCONNECTED AND STOPPED.")
    log.info("ℹ️ No market scans, order executions, or webhook triggers will run.")
    log.info("====================================================================================================")

if __name__ == "__main__":
    main()
