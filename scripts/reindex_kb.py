import argparse
import uuid

from app.db import session_local
from app.models import KBArticle
from app.services.ingest import ingest_kb_article


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rebuild KB chunks using the current sanitizer and chunking strategy."
    )
    parser.add_argument(
        "--tenant-id",
        type=uuid.UUID,
        help="Reindex only this tenant. Omit to reindex every tenant.",
    )
    parser.add_argument(
        "--allow-email",
        action="append",
        default=[],
        metavar="EMAIL",
        help=(
            "Preserve this explicitly trusted public business contact email. "
            "May be supplied more than once."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    allowed_emails = {email.strip().lower() for email in args.allow_email if email.strip()}

    db = session_local()
    try:
        query = db.query(KBArticle).order_by(KBArticle.tenant_id, KBArticle.id)
        if args.tenant_id:
            query = query.filter(KBArticle.tenant_id == args.tenant_id)

        # Load the article rows before ingest_kb_article commits individual
        # chunk updates. This avoids holding a streaming DB cursor across commits.
        articles = query.all()
        print(f"Reindexing {len(articles)} KB articles...")

        for index, article in enumerate(articles, start=1):
            ingest_kb_article(
                db,
                article,
                allowed_emails=allowed_emails,
            )
            if index % 25 == 0 or index == len(articles):
                print(f"Processed {index}/{len(articles)} articles")

        print("KB reindex completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
