from pieces.dexanalyzer_scraper import scrape_dexanalyzer

def main():
    # Ask for user input
    token_hash = input("Enter the token hash (or type 'exit' to quit): ").strip()
    if token_hash.lower() == 'exit':
        print("Exiting...")
        return

    # Ask if the user wants to save the HTML content
    save_html_input = input("Do you want to save the HTML content? (yes/no): ").strip().lower()
    save_html = save_html_input in ['yes', 'y']

    # Run the scraper
    scam_detected = scrape_dexanalyzer(token_hash, save_html=save_html)

    # Print the result
    if scam_detected:
        print(f"Alert: DexAnalyzer detected a SCAM for token {token_hash}.")
    else:
        print(f"No alert: DexAnalyzer did not detect a scam for token {token_hash}.")

if __name__ == "__main__":
    main()
