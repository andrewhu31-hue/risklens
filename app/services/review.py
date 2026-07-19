from app.analytics.factors import factor_report
from app.analytics.risk import risk_report
from app.services.ai import ask_claude
from app.services.context import PortfolioContext

SYSTEM_PROMPT = (
    "You are a quantitative portfolio risk analyst. You are given the actual computed "
    "risk statistics for a user's portfolio. Reference the real numbers directly in your "
    "answer. Do not invent numbers that were not provided. Be concise and specific."
)


def build_context_block(ctx: PortfolioContext) -> str:
    risk = risk_report(ctx.returns[ctx.tickers], ctx.weights, ctx.returns[ctx.benchmark])
    factors = factor_report(ctx.returns[ctx.tickers], ctx.weights)

    top_contributors = factors["risk_contributions"][:3]
    top_factor = factors["factors"][0]
    sorted_weights = sorted(ctx.weights.items(), key=lambda kv: -kv[1])

    lines = [
        f"Portfolio: {ctx.portfolio.name} ({len(ctx.tickers)} holdings, benchmark {ctx.benchmark})",
        "Weights: " + ", ".join(f"{t} {w:.1%}" for t, w in sorted_weights),
        f"Annualized return: {risk['annualized_return']:.2%}",
        f"Annualized volatility: {risk['annualized_volatility']:.2%}",
        f"Sharpe ratio: {risk['sharpe_ratio']:.2f}",
        f"Sortino ratio: {risk['sortino_ratio']:.2f}",
        f"Max drawdown: {risk['max_drawdown']:.2%}",
        f"95% 1-day VaR: {risk['var_95']:.2%}, CVaR: {risk['cvar_95']:.2%}",
        f"Beta vs {ctx.benchmark}: {risk['beta']:.2f}",
        f"Dominant risk factor explains {top_factor['variance_explained']:.1%} of portfolio variance",
        "Top risk contributors: "
        + ", ".join(f"{c['ticker']} ({c['risk_contribution_pct']:.1%} of portfolio risk)" for c in top_contributors),
    ]
    return "\n".join(lines)


def generate_debrief(ctx: PortfolioContext) -> str:
    context_block = build_context_block(ctx)
    prompt = (
        f"{context_block}\n\n"
        "Write a 4-6 sentence portfolio risk debrief. Call out the biggest concentration or "
        "factor-exposure risk, whether the portfolio is being paid for the risk it's taking "
        "(Sharpe/Sortino), and one concrete diversification suggestion."
    )
    return ask_claude(SYSTEM_PROMPT, prompt)


def answer_question(ctx: PortfolioContext, question: str) -> str:
    context_block = build_context_block(ctx)
    prompt = f"{context_block}\n\nQuestion: {question}"
    return ask_claude(SYSTEM_PROMPT, prompt, max_tokens=500)
