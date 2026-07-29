from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.limiter import limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user
from app.services.context import load_portfolio_context
from app.services.review import answer_question

router = APIRouter(prefix="/portfolios", tags=["ask"])


class AskBody(BaseModel):
    question: str


@router.post("/{portfolio_id}/ask")
@limiter.limit("20/minute")
def ask(
    request: Request,
    portfolio_id: str,
    body: AskBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ctx = load_portfolio_context(db, portfolio_id, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        answer = answer_question(ctx, body.question)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"question": body.question, "answer": answer}
