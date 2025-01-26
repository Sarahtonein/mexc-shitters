import requests
import time
import json
import os
from datetime import datetime, timedelta, timezone

GET_URL = "https://contract.mexc.com/api/v1/contract/detail"
PRICE_URL = "https://contract.mexc.com/api/v1/contract/ticker?symbol={}"
POST_URL = os.getenv("POST_URL")  
TRACKED_TOKENS_FILE = "tracked_tokens.json"


def load_tracked_tokens():
    try:
        with open(TRACKED_TOKENS_FILE, "r") as file:
            content = file.read().strip()
            if content:
                return json.loads(content)
            else:
                return {}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading tracked tokens: {e}")
        return {}


def save_tracked_tokens(tokens):
    try:
        with open(TRACKED_TOKENS_FILE, "w") as file:
            json.dump(tokens, file, indent=4)
    except Exception as e:
        print(f"Error saving tokens to file: {e}")


def get_tokens():
    try:
        response = requests.get(GET_URL)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("data", [])
    except requests.RequestException as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Error fetching tokens: {e}")
        return []


def get_token_price(symbol):
    try:
        response = requests.get(PRICE_URL.format(symbol))
        response.raise_for_status()
        data = response.json()
        return float(data.get("lastPrice", 0))
    except requests.RequestException as e:
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] Error fetching price for {symbol}: {e}"
        )
        return None


def post_price_change(token_name, initial_price, current_price, price_change):
    payload = {
        "token_name": token_name,
        "initial_price": initial_price,
        "current_price": current_price,
        "price_change": price_change,
    }
    try:
        response = requests.post(POST_URL, json=payload)
        response.raise_for_status()
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] POST successful for {token_name}: {response.status_code}"
        )
    except requests.RequestException as e:
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] Error sending POST request for {token_name}: {e}"
        )


def check_price_changes(tracked_tokens):
    current_time = datetime.now(timezone.utc)
    to_remove = []

    for token_name, data in tracked_tokens.items():
        initial_time = datetime.fromisoformat(data["time"])
        if current_time >= initial_time + timedelta(hours=8):
            initial_price = data["price"]
            current_price = get_token_price(token_name)

            if current_price is not None:
                price_change = ((current_price - initial_price) / initial_price) * 100
                print(
                    f"Token: {token_name}, Initial Price: {initial_price}, Current Price: {current_price}, Change: {price_change:.2f}%"
                )
                post_price_change(
                    token_name, initial_price, current_price, price_change
                )

    #            to_remove.append(token_name)

    for token_name in to_remove:
        del tracked_tokens[token_name]
    save_tracked_tokens(tracked_tokens)


def find_new_tokens():
    tracked_tokens = load_tracked_tokens()

    while True:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Starting new iteration")
        tokens = get_tokens()

        if tokens:
            current_time = datetime.now(timezone.utc)
            one_hour_ago = current_time - timedelta(hours=1)

            for token in tokens:
                if not isinstance(token, dict):
                    print(f"Unexpected token format: {token}")
                    continue

                create_time_ms = token.get("createTime", 0)
                create_time = datetime.fromtimestamp(
                    create_time_ms / 1000, timezone.utc
                )

                if create_time >= one_hour_ago:
                    token_name = token.get("symbol")
                    token_link = f"https://futures.mexc.com/exchange/{token_name}?type=linear_swap"

                    if token_name not in tracked_tokens:
                        current_price = get_token_price(token_name)
                        if current_price is not None:
                            tracked_tokens[token_name] = {
                                "price": current_price,
                                "time": current_time.isoformat(),
                            }
                            print(
                                f"Tracking new token: {token_name} at price {current_price}"
                            )
                            save_tracked_tokens(tracked_tokens)
        else:
            print("No new tokens found")

        check_price_changes(tracked_tokens)

        time.sleep(25)


if __name__ == "__main__":
    find_new_tokens()
