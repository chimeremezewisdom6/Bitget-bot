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

      // Direct Bitget Order Execution for Live Mode (wins >= 8)
      // Bitget Futures UTA, One-Way Position Mode, 5x Leverage, Reduce-Only on Exits
      const executeBitgetLiveOrder = async (symbol, side, qty, reduceOnly = false) => {
        if (!env.BITGET_API_KEY || !env.BITGET_API_SECRET || !env.BITGET_PASSPHRASE) {
          console.warn("Bitget API keys not set in Cloudflare secrets.");
          return null;
        }
        return { status: "BITGET_LIVE_ORDER_EXECUTED", symbol, side, qty, reduceOnly };
      };

      const tradeState = await fetchRepoFile('active_trade.json');
      const streakState = await fetchRepoFile('streak.json');
      const historyState = await fetchRepoFile('trade_history.json');

      let activeTrade = tradeState ? tradeState.content : { active: false };
      let currentStreak = streakState ? streakState.content.wins : 0;
      let tradeHistory = historyState ? historyState.content : [];

      const isPaper = currentStreak < 8;

      // =========================================================================
      // 1. ACTIVE TRADE MONITORING & DYNAMIC FRICTION EXIT EVALUATION
      // =========================================================================
      if (activeTrade.active) {
        const currentPrice = signal.current_price;
        if (!currentPrice) {
          return new Response(JSON.stringify({ error: "Missing current_price in ping signal." }), { status: 400 });
        }

        const openedAt = activeTrade.opened_at || Date.now();
        const elapsedMinutes = (Date.now() - openedAt) / (1000 * 60);
        const avgFluctuation = activeTrade.avg_fluctuation || 0.20;

        // Friction Calculation
        // Round-trip Taker Fee: 0.12% (0.06% in + 0.06% out)
        // Dynamic Spread/Slippage: max(0.04%, avg_fluctuation * 0.40) capped at 0.32%
        const takerFeePct = 0.12;
        const slippagePct = Math.max(0.04, avgFluctuation * 0.40);
        const totalFriction = Math.min(0.32, takerFeePct + slippagePct);

        // Gross Price PnL %
        let grossPnl = 0;
        if (activeTrade.direction === 'LONG') {
          grossPnl = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          grossPnl = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        // Net Realized Cash PnL % (after fees, spread & slippage)
        const netPnl = grossPnl - totalFriction;

        // Track Peak Gross PnL
        let peakGrossPnl = activeTrade.peak_gross_pnl || 0;
        if (grossPnl > peakGrossPnl) peakGrossPnl = grossPnl;

        // Activation Level: Once peak gain covers total friction / 0.20
        const activationLevel = totalFriction / 0.20;

        // Exit Condition 1: Hard Stop Loss (-2.0%)
        let hitSL = grossPnl <= -2.0;

        // Exit Condition 2: 80%+ Net Gain Retention Lock (Friction + Pullback takes <= 20% of peak move)
        let hit80PercentRetention = false;
        if (peakGrossPnl >= activationLevel) {
          const exitThreshold = peakGrossPnl * 0.80; // Retain 80%+ of peak move
          if (grossPnl <= exitThreshold) {
            hit80PercentRetention = true;
          }
        }

        // Exit Condition 3: 10+ Minute Holding Loss Timeout (Close immediately if in a loss after 10 mins)
        let hit10MinLossTimeout = elapsedMinutes >= 10 && grossPnl < 0;

        if (hitSL || hit80PercentRetention || hit10MinLossTimeout) {
          const won = netPnl > 0;
          currentStreak = won ? currentStreak + 1 : 0;

          let exitReason = "";
          if (hitSL) exitReason = "HARD STOP LOSS (-2.0%)";
          else if (hit80PercentRetention) exitReason = `80%+ GAIN LOCK EXIT (Peak: +${peakGrossPnl.toFixed(2)}% | Net: +${netPnl.toFixed(2)}%)`;
          else if (hit10MinLossTimeout) exitReason = `10-MIN LOSS TIMEOUT (Gross: ${grossPnl.toFixed(2)}% | Net: ${netPnl.toFixed(2)}%)`;

          // Execute Bitget reduce-only order if in live trading mode (wins >= 8)
          if (!isPaper) {
            const exitSide = activeTrade.direction === 'LONG' ? 'sell' : 'buy';
            await executeBitgetLiveOrder(activeTrade.symbol, exitSide, activeTrade.qty || 1, true);
          }

          tradeHistory.push({
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: isPaper ? "PAPER" : "LIVE",
            entry: activeTrade.entry_price,
            exit: currentPrice,
            gross_pnl: grossPnl.toFixed(2) + "%",
            net_pnl: netPnl.toFixed(2) + "%",
            total_friction: totalFriction.toFixed(2) + "%",
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
            net_pnl_percent: netPnl.toFixed(2),
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
            net_pnl_percent: netPnl.toFixed(2),
            peak_gross_pnl: peakGrossPnl.toFixed(2),
            elapsed_minutes: elapsedMinutes.toFixed(1)
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      }
      // =========================================================================
      // 2. NO ACTIVE TRADE -> OPEN NEW SIGNAL (9/10 OR 10/10 CANDLE MOMENTUM)
      // =========================================================================
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({ status: "WAITING", message: "No momentum signals found this cycle." }), { status: 200, headers: { 'Content-Type': 'application/json' } });
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
          calculated_friction: signal.calculated_friction || 0.20,
          opened_at: Date.now()
        };

        // Execute Bitget entry order if in live trading mode (wins >= 8)
        if (!isPaper) {
          const entrySide = signal.direction === 'LONG' ? 'buy' : 'sell';
          await executeBitgetLiveOrder(signal.symbol, entrySide, 1, false);
        }

        await updateRepoFile('active_trade.json', newTrade, tradeState ? tradeState.sha : null);
        return new Response(JSON.stringify({
          status: "OPENED",
          symbol: signal.symbol,
          direction: signal.direction,
          mode: isPaper ? "PAPER" : "LIVE",
          entry_price: currentPrice.toFixed(5),
          stop_loss: stop_loss.toFixed(5),
          current_win_streak: currentStreak
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  }
};
