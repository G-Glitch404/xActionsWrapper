import os
import uvicorn

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    """ start the api server """
    uvicorn.run(
        "src.api:app",
        host=os.environ["HOST"],
        port=int(os.environ["PORT"]),
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
