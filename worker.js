export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method Not Allowed' }), { status: 405, headers: { 'Content-Type': 'application/json' } });
    }

    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
    }

    try {
      const signal = await request.json();

      const GH_DOMAIN = 'api.' + 'github' + '.com';
      const GH_BASE = `https://${GH_DOMAIN}/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents`;

      const fetchRepoFile = async (filename) => {
        const repoUrl = `${GH_BASE}/${filename}`;
        const res = await fetch(repoUrl, {
          headers: {
            'Authorization': `token ${env.GITHUB_PAT}`,
            'User-Agent': 'CF-Worker',
            'Accept': 'application/vnd.github.v3+json'
          }
        });
        if (!res.ok) return null;
        const data = await res.json();
        return { sha: data.sha, content: JSON.parse(atob(data.content)) };
      };

      const updateRepoFile = async (filename, content, sha) => {
        const repoUrl = `${GH_BASE}/${filename}`;
        await fetch(repoUrl, {
          method: 'PUT',
          headers: {
            'Authorization': `token ${env.GITHUB_PAT}`,
            'User-Agent': 'CF-Worker',
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.github.v3+json'
          },
          body: JSON.stringify({
            message: `Automated Bot Update: ${filename}`,
            content: btoa(JSON.stringify(content, null, 2)),
            sha: sha
          })
        });
      };

      const tradeState = await fetchRepoFile('active_trade.json');
      const streakState = await fetchRepoFile('streak.json');
      const historyState = await fetchRepoFile('trade_history.json');

      let activeTrade = tradeState ? tradeState.content : { active: false };
      let currentStreak = streakState ? streakState.content.wins : 0;
      let tradeHistory = historyState ? historyState.content : [];

      // PAPER MODE LOCK: Must achieve 8 wins in a row before going live
      const isPaper = currentStreak < 8;

      // =========================================================================
      // 1. ACTIVE TRADE MONITORING & DYNAMIC MOMENTUM EXITS
      // =========================================================================
      if (activeTrade.active) {
        const currentPrice = signal.current_price;
        if (!currentPrice) {
          return new Response(JSON.stringify({ error: "Missing current_price in ping signal." }), { status: 400 });
        }

        const openedAt = activeTrade.opened_at || Date.now();
        const elapsedMinutes = (Date.now() - openedAt) / (1000 * 60);

        // Calculate Gross Price PnL %
        let grossPnl = 0;
        if (activeTrade.direction === 'LONG') {
          grossPnl = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          grossPnl = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        // Track Peak Gross PnL
        let peakGrossPnl = activeTrade.peak_gross_pnl || 0;
        if (grossPnl > peakGrossPnl) peakGrossPnl = grossPnl;

        // =========================================================================
        // SMART DYNAMIC TAKE-PROFIT LOGIC (Rides Parabolic Breakouts Beyond +1.0%!)
        // =========================================================================
        // Rule A: Profit target threshold met (grossPnl >= 1.00%)
        let inProfitZone = grossPnl >= 1.00;

        // Rule B: Dynamic Trailing Stop -- If peak reached >= 1.50% and drops 0.40% off peak, lock profit!
        let trailingPullbackTriggered = peakGrossPnl >= 1.50 && (peakGrossPnl - grossPnl) >= 0.40;

        // Rule C: Standard 5-Minute Evaluation Exit -- If profit is >= 1.00% at check interval, exit & lock gains!
        let hitTakeProfit = inProfitZone && (trailingPullbackTriggered || elapsedMinutes >= 4.0 || grossPnl >= 3.00);

        // EXIT CONDITION 2: 10-MINUTE STAGNANT PROFIT TIMEOUT (<0.50% Gross PnL at 10+ mins)
        let hit10MinStagnantProfitExit = elapsedMinutes >= 10 && grossPnl > 0 && grossPnl < 0.50 && !hitTakeProfit;

        // EXIT CONDITION 3: FAST LOSS TIMEOUT (< 6 mins elapsed and loss > 1.0%, close immediately!)
        let hitFastLossExit = elapsedMinutes < 6 && grossPnl <= -1.00;

        // EXIT CONDITION 4: HARD STOP LOSS (-2.0%)
        let hitSL = grossPnl <= -2.00;

        // EXIT CONDITION 5: 10+ MINUTE HOLDING LOSS TIMEOUT (Gross PnL <= 0)
        let hit10MinLossTimeout = elapsedMinutes >= 10 && grossPnl <= 0;

        if (hitTakeProfit || hit10MinStagnantProfitExit || hitFastLossExit || hitSL || hit10MinLossTimeout) {

          // STRICT WIN THRESHOLD RULE:
          // Any gross PnL < 0.21% (after 0.20% friction fee) yields <= +0.00% Net Profit -> Counted as LOSS!
          const won = grossPnl >= 0.21;
          currentStreak = won ? currentStreak + 1 : 0;

          const netCashProfit = (grossPnl - 0.20).toFixed(2);

          let exitReason = "";
          if (hitTakeProfit) {
            exitReason = `1.0% TAKE PROFIT TARGET HIT (+${grossPnl.toFixed(2)}% Gross | Net Cash Profit: +${netCashProfit}%) -> Scanning next coin`;
          } else if (hit10MinStagnantProfitExit) {
            exitReason = `10-MIN STAGNANT PROFIT EXIT (<0.50% Gross at 10m | Exit: +${grossPnl.toFixed(2)}% | Net Cash Profit: +${netCashProfit}%)`;
          } else if (hitFastLossExit) {
            exitReason = `FAST LOSS EXIT (<6m Loss >1.0% | Exit: ${grossPnl.toFixed(2)}% | Cut fast loss)`;
          } else if (hitSL) {
            exitReason = "HARD STOP LOSS (-2.0%)";
          } else if (hit10MinLossTimeout) {
            exitReason = `10-MIN LOSS TIMEOUT (Gross: ${grossPnl.toFixed(2)}%)`;
          }

          if (!won && grossPnl > 0 && grossPnl < 0.21) {
            exitReason += ` | [STREAK RESET TO 0: Gross PnL +${grossPnl.toFixed(2)}% < 0.21% friction threshold]`;
          }

          tradeHistory.push({
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: isPaper ? "PAPER" : "LIVE",
            entry: activeTrade.entry_price,
            exit: currentPrice,
            gross_pnl: grossPnl.toFixed(2) + "%",
            net_pnl: netCashProfit + "%",
            won: won,
            reason: exitReason,
            elapsed_minutes: elapsedMinutes.toFixed(1),
            streak_after_trade: currentStreak,
            date: new Date().toISOString()
          });

          await updateRepoFile('streak.json', { wins: currentStreak, last_updated: new Date().toISOString() }, streakState ? streakState.sha : null);
          await updateRepoFile('active_trade.json', { active: false }, tradeState ? tradeState.sha : null);
          if (historyState) await updateRepoFile('trade_history.json', tradeHistory, historyState.sha);

          return new Response(JSON.stringify({
            status: "CLOSED",
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: isPaper ? "PAPER" : "LIVE",
            entry_price: activeTrade.entry_price,
            exit_price: currentPrice,
            gross_pnl_percent: grossPnl.toFixed(2),
            net_cash_profit: netCashProfit + "%",
            peak_gross_pnl: peakGrossPnl.toFixed(2),
            reason: exitReason,
            won: won,
            new_win_streak: currentStreak
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        } else {
          activeTrade.peak_gross_pnl = peakGrossPnl;
          await updateRepoFile('active_trade.json', activeTrade, tradeState ? tradeState.sha : null);
          return new Response(JSON.stringify({
            status: "HOLDING",
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            entry_price: activeTrade.entry_price,
            current_price: currentPrice,
            gross_pnl_percent: grossPnl.toFixed(2),
            peak_gross_pnl: peakGrossPnl.toFixed(2),
            elapsed_minutes: elapsedMinutes.toFixed(1)
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      }
      // =========================================================================
      // 2. NO ACTIVE TRADE -> OPEN NEW SIGNAL
      // =========================================================================
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({
            status: "WAITING",
            message: "No momentum signals found."
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        const currentPrice = signal.current_price;
        const stop_loss = signal.direction === 'LONG' ? currentPrice * 0.98 : currentPrice * 1.02;

        const newTrade = {
          active: true,
          symbol: signal.symbol,
          direction: signal.direction,
          mode: isPaper ? "PAPER" : "LIVE",
          entry_price: currentPrice,
          stop_loss: stop_loss,
          peak_gross_pnl: 0,
          avg_fluctuation: signal.avg_fluctuation || 0.20,
          leverage: 5,
          position_mode: "one_way",
          reduce_only: true,
          opened_at: Date.now()
        };

        await updateRepoFile('active_trade.json', newTrade, tradeState ? tradeState.sha : null);
        return new Response(JSON.stringify({
          status: "OPENED",
          symbol: signal.symbol,
          direction: signal.direction,
          mode: isPaper ? "PAPER" : "LIVE",
          entry_price: currentPrice.toFixed(5),
          stop_loss: stop_loss.toFixed(5),
          current_win_streak: currentStreak,
          leverage: "5x",
          position_mode: "one_way (single_hold)",
          reduce_only: true
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  }
};
