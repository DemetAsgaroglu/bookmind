"""Komut satiri arayuzu.

    python -m bookmind.cli chat --user demet
    python -m bookmind.cli library add book_042 --user demet --rating 5
    python -m bookmind.cli library list --user demet
    python -m bookmind.cli search "uzayda gecen bir roman"
"""

import argparse

from .services import create_services


def _print_library(items: list[dict]) -> None:
    if not items:
        print("Kutuphane bos.")
        return
    for i in items:
        rating = f" | puan: {i['rating']}" if i["rating"] else ""
        print(f"{i['id']} | {i['title']} - {i['author']} | {i['status']}{rating}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="bookmind")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Agent ile sohbet")
    chat.add_argument("--user", default="demo")
    chat.add_argument("--debug", action="store_true", help="Arac cagrilarini goster")

    search = sub.add_parser("search", help="Anlamsal kitap aramasi")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)

    lib = sub.add_parser("library", help="Kisisel kutuphane")
    lib_sub = lib.add_subparsers(dest="action", required=True)
    lib_list = lib_sub.add_parser("list")
    lib_list.add_argument("--user", default="demo")
    lib_add = lib_sub.add_parser("add")
    lib_add.add_argument("book_id")
    lib_add.add_argument("--user", default="demo")
    lib_add.add_argument("--status", default="okudum", choices=["okudum", "okuyorum", "okuyacagim"])
    lib_add.add_argument("--rating", type=int, choices=range(1, 6))
    lib_rm = lib_sub.add_parser("remove")
    lib_rm.add_argument("book_id")
    lib_rm.add_argument("--user", default="demo")

    args = parser.parse_args()
    services = create_services(with_agent=args.command == "chat")

    if args.command == "search":
        for book_id, score in services.store.search(args.query, k=args.limit):
            book = services.db.get_book(book_id)
            print(f"{score:.3f} | {book_id} | {book['title']} - {book['author']} ({book['genre']})")

    elif args.command == "library":
        if args.action == "list":
            _print_library(services.db.get_library(args.user))
        elif args.action == "add":
            services.db.add_to_library(args.user, args.book_id, args.status, args.rating)
            print(f"{args.book_id} kutuphaneye eklendi.")
        elif args.action == "remove":
            removed = services.db.remove_from_library(args.user, args.book_id)
            print("Silindi." if removed else "Kitap kutuphanede yok.")

    elif args.command == "chat":
        print("BookMind - cikmak icin 'q' yazin, sohbeti sifirlamak icin '/yeni'.")
        while True:
            try:
                message = input("\nSiz: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if message.lower() in {"q", "quit", "exit"}:
                break
            if message == "/yeni":
                services.agent.reset(args.user)
                print("Sohbet sifirlandi.")
                continue
            try:
                result = services.agent.chat(args.user, message)
            except Exception as exc:  # noqa: BLE001 - API hatasinda sohbet kapanmasin
                print(f"\nHata: {exc}")
                continue
            if args.debug and result.tool_calls:
                for call in result.tool_calls:
                    print(f"  [arac] {call['name']} {call['args']}")
            print(f"\nBookMind: {result.reply}")


if __name__ == "__main__":
    main()
