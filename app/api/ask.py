from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import load_context
from app.limiter import AI_LIMIT, limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user
from app.services.review import answer_question

router = APIRouter(prefix="/portfolios", tags=["ask"])

MAX_QUESTION_CHARS = 2000


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


@router.post("/{portfolio_id}/ask")
@limiter.limit(AI_LIMIT)
def ask(
    request: Request,
    portfolio_id: str,
    body: AskBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = load_context(db, portfolio_id, current_user.id)
    try:
        answer = answer_question(ctx, body.question)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"question": body.question, "answer": answer}
