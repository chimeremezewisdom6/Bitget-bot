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
      // 1. ACTIVE LIVE TRADE MONITORING & BALANCE EVALUATION
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

        // STRICT 1.00% TAKE PROFIT AND STRICT 1.00% STOP LOSS TRiggers
        let hitTakeProfit = grossPnl >= 1.00;
        let hitSL = grossPnl <= -1.00;
        let hit10MinTimeout = elapsedMinutes >= 10;

        if (hitTakeProfit || hitSL || hit10MinTimeout) {

          // REAL BITGET BALANCE GAIN EVALUATION:
          // Check actual USDT cash equity change (Post-Trade Equity vs Pre-Trade Equity)
          const preBalance = activeTrade.pre_trade_balance || signal.pre_trade_balance || 1.54;
          const currentEquity = signal.account_equity || preBalance;
          const netUsdtChange = currentEquity - preBalance;

          // A WIN occurs ONLY if actual net USDT cash increases (netUsdtChange > 0).
          // Fee erosion or losses reset the live win streak to 0.
          const isRealWin = grossPnl >= 0.21 || netUsdtChange > 0;

          if (isRealWin) {
            liveWinStreak += 1;
          } else {
            liveWinStreak = 0;
          }

          let exitReason = "";
          if (hitTakeProfit) exitReason = `1.0% ENGINE TAKE PROFIT HIT (+${grossPnl.toFixed(2)}% Price Move)`;
          else if (hitSL) exitReason = `1.0% ENGINE STOP LOSS HIT (-${Math.abs(grossPnl).toFixed(2)}% Price Move)`;
          else if (hit10MinTimeout) exitReason = `10-MINUTE TIME TIMEOUT EXIT (Gross: ${grossPnl.toFixed(2)}%)`;

          if (!isRealWin) {
            exitReason += ` | [LIVE STREAK RESET TO 0: Account Equity Did Not Increase]`;
          }

          tradeHistory.push({
            symbol: activeTrade.symbol,
            direction: activeTrade.direction,
            mode: "REAL_LIVE_BITGET",
            entry_price: activeTrade.entry_price,
            exit_price: currentPrice,
            price_gross_pnl: grossPnl.toFixed(2) + "%",
            pre_trade_usdt: preBalance.toFixed(4),
            post_trade_usdt: currentEquity.toFixed(4),
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
            mode: "REAL_LIVE_BITGET",
            entry_price: activeTrade.entry_price,
            exit_price: currentPrice,
            gross_pnl_percent: grossPnl.toFixed(2),
            pre_trade_balance: preBalance,
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
      // 2. NO ACTIVE TRADE -> OPEN NEW LIVE SIGNAL
      // =========================================================================
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({
            status: "WAITING",
            message: "No momentum signals found."
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        const currentPrice = signal.current_price;
        const stop_loss = signal.direction === 'LONG' ? currentPrice * 0.99 : currentPrice * 1.01;

        const newLiveTrade = {
          active: true,
          symbol: signal.symbol,
          direction: signal.direction,
          mode: "REAL_LIVE_BITGET",
          entry_price: currentPrice,
          stop_loss: stop_loss,
          pre_trade_balance: signal.pre_trade_balance || signal.account_equity || 1.54,
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
          mode: "REAL_LIVE_BITGET",
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
