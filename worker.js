export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) return new Response('Unauthorized', { status: 401 });

    try {
      const signal = await request.json();
      
      const getGithubFile = async (filename) => {
        const gurl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        const res = await fetch(gurl, {
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Accept': 'application/vnd.github.v3+json' }
        });
        if (!res.ok) return null;
        const data = await res.json();
        return { sha: data.sha, content: JSON.parse(atob(data.content)) };
      };

      const updateGithubFile = async (filename, content, sha) => {
        const gurl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        await fetch(gurl, {
          method: 'PUT',
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
          body: JSON.stringify({ message: `Update ${filename}`, content: btoa(JSON.stringify(content)), sha: sha })
        });
      };

      const tradeState = await getGithubFile('active_trade.json');
      const streakState = await getGithubFile('streak.json');
      const historyState = await getGithubFile('trade_history.json');
      
      let activeTrade = tradeState ? tradeState.content : { active: false };
      let currentStreak = streakState ? streakState.content.wins : 0;
      let tradeHistory = historyState ? historyState.content : [];
      let isLiveMode = currentStreak >= 8;

      // ==========================================
      // IF TRADE ACTIVE -> CHECK TP/SL AND DYNAMIC TRAILING
      // ==========================================
      if (activeTrade.active) {
        // 🚨 USE PRICE PASSED FROM GITHUB 🚨
        const currentPrice = signal.current_price; 
        
        if (!currentPrice) {
            throw new Error("No current price provided by GitHub.");
        }

        let pnlPercent = 0;
        
        if (activeTrade.direction === 'LONG') {
          pnlPercent = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          pnlPercent = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        let peakPnl = activeTrade.peak_pnl || 0;
        if (pnlPercent > peakPnl) peakPnl = pnlPercent;

        let hitSL = false;
        if (activeTrade.direction === 'LONG') {
            if (currentPrice <= activeTrade.stop_loss) hitSL = true;
        } else {
            if (currentPrice >= activeTrade.stop_loss) hitSL = true;
        }

        // DYNAMIC REBOUND TRAILING STOP
        let isFading = false;
        let trailing_stop_pnl = -100; 
        
        if (peakPnl >= 2.0) {
            trailing_stop_pnl = peakPnl - 0.5;
            if (pnlPercent <= trailing_stop_pnl) isFading = true;
        } else if (peakPnl >= 1.0) {
            trailing_stop_pnl = Math.max(0.5, peakPnl * 0.6);
            if (pnlPercent <= trailing_stop_pnl) isFading = true;
        }

        if (hitSL || isFading) {
          const won = pnlPercent > 0;
          currentStreak = won ? currentStreak + 1 : 0;
          let reason = hitSL ? "STOP LOSS (2%)" : `TRAILING REBOUND (${trailing_stop_pnl.toFixed(2)}%)`;

          tradeHistory.push({
              symbol: activeTrade.symbol,
              direction: activeTrade.direction,
              entry: activeTrade.entry_price,
              exit: currentPrice,
              pnl: pnlPercent.toFixed(2) + "%",
              won: won,
              reason: reason,
              date: new Date().toISOString()
          });

          if (tradeHistory.length > 50) tradeHistory.shift();

          await updateGithubFile('streak.json', { wins: currentStreak }, streakState.sha);
          await updateGithubFile('active_trade.json', { active: false }, tradeState.sha);
          
          if (historyState) {
              await updateGithubFile('trade_history.json', tradeHistory, historyState.sha);
          } else {
              const gurl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/trade_history.json`;
              await fetch(gurl, {
                method: 'PUT',
                headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
                body: JSON.stringify({ message: `Create trade_history.json`, content: btoa(JSON.stringify(tradeHistory)) })
              });
          }

          return new Response(JSON.stringify({ 
            status: "CLOSED", symbol: activeTrade.symbol, direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2), peak_pnl: peakPnl.toFixed(2),
            reason: reason, won: won, streak: currentStreak 
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        } else {
          activeTrade.peak_pnl = peakPnl;
          await updateGithubFile('active_trade.json', activeTrade, tradeState.sha);

          return new Response(JSON.stringify({ 
            status: "HOLDING", symbol: activeTrade.symbol, direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2), peak_pnl: peakPnl.toFixed(2),
            trailing_stop: peakPnl >= 1.0 ? trailing_stop_pnl.toFixed(2) : "Not Active"
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      } 
      // ==========================================
      // IF NO TRADE ACTIVE -> OPEN NEW
      // ==========================================
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({ status: "WAITING", message: "No signal found." }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        const currentPrice = signal.current_price; 
        
        let stop_loss;
        if (signal.direction === 'LONG') {
            stop_loss = currentPrice * 0.98;
        } else {
            stop_loss = currentPrice * 1.02;
        }

        const newTrade = {
          active: true, symbol: signal.symbol, direction: signal.direction,
          entry_price: currentPrice, stop_loss: stop_loss, peak_pnl: 0, opened_at: Date.now()
        };

        await updateGithubFile('active_trade.json', newTrade, tradeState.sha);

        return new Response(JSON.stringify({ 
          status: "OPENED", symbol: signal.symbol, direction: signal.direction,
          entry_price: currentPrice.toFixed(5), stop_loss: stop_loss.toFixed(5),
          mode: isLiveMode ? "LIVE" : "PAPER"
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  },
};
