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
            message: `Automated Live Bot Update: ${filename}`,
            content: btoa(JSON.stringify(content, null, 2)),
            sha: sha
          })
        });
      };

      const tradeState = await fetchRepoFile('live_active_trade.json');
      const streakState = await fetchRepoFile('live_streak.json');
      const historyState = await fetchRepoFile('live_trade_history.json');

      let activeTrade = tradeState ? tradeState.content : { active: false };
      let liveWinStreak = streakState ? streakState.content.live_wins : 0;
      let tradeHistory = historyState ? historyState.content : [];

      // =========================================================================
      // 1. ACTIVE LIVE ABSORPTION TRADE MONITORING & BALANCE EVALUATION
      // =========================================================================
      if (activeTrade.active) {
        const currentPrice = signal.current_price;
        if (!currentPrice) {
          return new Response(JSON.stringify({ error: "Missing current_price in ping signal." }), { status: 400 });
        }

        const openedAt = activeTrade.opened_at || Date.now();
        const elapsedMinutes = (Date.now() - openedAt) / (1000 * 60);

        let grossPnl = 0;
        if (activeTrade.direction === 'LONG') {
          grossPnl = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          grossPnl = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        // STRICT 2.50% ENGINE TAKE PROFIT, -1.50% ENGINE STOP LOSS, AND 30-MIN TIMEOUT
        let hitTakeProfit = grossPnl >= 2.50;
        let hitSL = grossPnl <= -1.50;
        let hitTimeTimeout = elapsedMinutes >= 30;

        if (hitTakeProfit || hitSL || hitTimeTimeout) {

          const preBalance = activeTrade.pre_trade_balance || signal.pre_trade_balance || 1.32;
          const currentEquity = signal.account_equity || preBalance;
          const netUsdtChange = currentEquity - preBalance;

          // STRICT CASH WIN RULE:
          const isRealWin = netUsdtChange > 0;

          if (isRealWin) {
            liveWinStreak += 1;
          } else {
            liveWinStreak = 0;
          }

          let exitReason = "";
          if (hitTakeProfit) exitReason = `2.5% ENGINE TAKE PROFIT HIT (+${grossPnl.toFixed(2)}% Price Move)`;
          else if (hitSL) exitReason = `1.5% ENGINE STOP LOSS HIT (${grossPnl.toFixed(2)}% Price Move)`;
          else if (hitTimeTimeout) exitReason = `30-MINUTE ABSORPTION TIMEOUT EXIT (${grossPnl.toFixed(2)}% Price Move)`;

          if (!isRealWin) {
            exitReason += ` | [STREAK RESET TO 0: Real Cash Equity Decreased by $${Math.abs(netUsdtChange).toFixed(4)}]`;
          }

          tradeHistory.push({
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: "REAL_LIVE_CAPITAL_ABSORPTION",
            entry_price: activeTrade.entry_price,
            exit_price: currentPrice,
            price_gross_pnl: grossPnl.toFixed(2) + "%",
            pre_trade_usdt: preBalance.toFixed(4),
            post_trade_usdt: currentEquity.toFixed(4),
            net_usdt_change: netUsdtChange.toFixed(4),
            won: isRealWin,
            reason: exitReason,
            elapsed_minutes: elapsedMinutes.toFixed(1),
            live_win_streak_after: liveWinStreak,
            date: new Date().toISOString()
          });

          await updateRepoFile('live_streak.json', { live_wins: liveWinStreak, last_updated: new Date().toISOString() }, streakState ? streakState.sha : null);
          await updateRepoFile('live_active_trade.json', { active: false }, tradeState ? tradeState.sha : null);
          if (historyState) await updateRepoFile('live_trade_history.json', tradeHistory, historyState.sha);

          return new Response(JSON.stringify({
            status: "CLOSED",
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: "REAL_LIVE_CAPITAL_ABSORPTION",
            entry_price: activeTrade.entry_price,
            exit_price: currentPrice,
            gross_pnl_percent: grossPnl.toFixed(2),
            pre_trade_balance: preBalance,
            post_trade_balance: currentEquity,
            net_usdt_change: netUsdtChange.toFixed(4),
            reason: exitReason,
            won: isRealWin,
            live_win_streak: liveWinStreak
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        } else {
          await updateRepoFile('live_active_trade.json', activeTrade, tradeState ? tradeState.sha : null);
          return new Response(JSON.stringify({
            status: "HOLDING",
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            entry_price: activeTrade.entry_price,
            current_price: currentPrice,
            gross_pnl_percent: grossPnl.toFixed(2),
            elapsed_minutes: elapsedMinutes.toFixed(1),
            live_win_streak: liveWinStreak
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      }
      // =========================================================================
      // 2. NO ACTIVE TRADE -> OPEN NEW UNEXPLODED CAPITAL ABSORPTION SIGNAL
      // =========================================================================
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({
            status: "WAITING",
            message: "No unexploded capital absorption signals found."
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        const currentPrice = signal.current_price;
        const stop_loss = signal.direction === 'LONG' ? currentPrice * 0.985 : currentPrice * 1.015;

        const newLiveTrade = {
          active: true,
          symbol: signal.symbol,
          direction: signal.direction,
          mode: "REAL_LIVE_CAPITAL_ABSORPTION",
          entry_price: currentPrice,
          stop_loss: stop_loss,
          pre_trade_balance: signal.pre_trade_balance || signal.account_equity || 1.32,
          contract_size: signal.contract_size || "1",
          leverage: 5,
          position_mode: "one_way",
          reduce_only: true,
          opened_at: Date.now()
        };

        await updateRepoFile('live_active_trade.json', newLiveTrade, tradeState ? tradeState.sha : null);
        return new Response(JSON.stringify({
          status: "OPENED",
          symbol: signal.symbol,
          direction: signal.direction,
          mode: "REAL_LIVE_CAPITAL_ABSORPTION",
          entry_price: currentPrice.toFixed(5),
          stop_loss: stop_loss.toFixed(5),
          live_win_streak: liveWinStreak,
          leverage: "5x",
          position_mode: "one_way",
          reduce_only: true
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  }
};
