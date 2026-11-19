export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) return new Response('Unauthorized', { status: 401 });

    try {
      const signal = await request.json();
      
      const getGithubFile = async (filename) => {
        const url = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        const res = await fetch(url, {
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Accept': 'application/vnd.github.v3+json' }
        });
        if (!res.ok) return null;
        const data = await res.json();
        return { sha: data.sha, content: JSON.parse(atob(data.content)) };
      };

      const updateGithubFile = async (filename, content, sha) => {
        const url = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        await fetch(url, {
          method: 'PUT',
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
          body: JSON.stringify({ message: `Update ${filename}`, content: btoa(JSON.stringify(content)), sha: sha })
        });
      };

      const getPrice = async (sym) => {
        const res = await fetch(`https://api.bitget.com/api/v3/market/ticker?category=USDT-FUTURES&symbol=${sym}`);
        const data = await res.json();
        if (data.code === '00000' && data.data && data.data.length > 0) return parseFloat(data.data[0].lastPr);
        throw new Error(`Failed to get price for ${sym}`);
      };

      const tradeState = await getGithubFile('active_trade.json');
      const streakState = await getGithubFile('streak.json');
      
      let activeTrade = tradeState ? tradeState.content : { active: false };
      let currentStreak = streakState ? streakState.content.wins : 0;
      let isLiveMode = currentStreak >= 8;

      // ==========================================
      // IF A TRADE IS ACTIVE -> CHECK HOLD OR CLOSE
      // ==========================================
      if (activeTrade.active) {
        const currentPrice = await getPrice(activeTrade.symbol);
        let pnlPercent = 0;
        
        if (activeTrade.direction === 'LONG') {
          pnlPercent = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          pnlPercent = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        // Update Peak PnL
        let peakPnl = activeTrade.peak_pnl || 0;
        if (pnlPercent > peakPnl) {
          peakPnl = pnlPercent;
        }

        // EXIT CONDITIONS: Stop Loss (Losing) or Trailing Stop (Fading by 0.2% from peak)
        const isLosing = pnlPercent <= 0;
        const isFading = peakPnl > 0.3 && pnlPercent < (peakPnl - 0.2);
        
        if (isLosing || isFading) {
          const won = pnlPercent > 0;
          currentStreak = won ? currentStreak + 1 : 0;

          // If live mode, place a real CLOSE order (Reduce Only)
          if (isLiveMode) {
            // (Live close logic omitted)
          }

          await updateGithubFile('streak.json', { wins: currentStreak }, streakState.sha);
          await updateGithubFile('active_trade.json', { active: false }, tradeState.sha);

          return new Response(JSON.stringify({ 
            status: "CLOSED", 
            symbol: activeTrade.symbol, 
            direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2),
            peak_pnl: peakPnl.toFixed(2),
            reason: isLosing ? "STOP LOSS" : "TRAILING STOP",
            won: won,
            streak: currentStreak 
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        } 
        // If not closing, we HOLD and update the peak
        else {
          activeTrade.peak_pnl = peakPnl;
          await updateGithubFile('active_trade.json', activeTrade, tradeState.sha);

          return new Response(JSON.stringify({ 
            status: "HOLDING", 
            symbol: activeTrade.symbol, 
            direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2),
            peak_pnl: peakPnl.toFixed(2)
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      } 
      
      // ==========================================
      // IF NO TRADE IS ACTIVE -> OPEN A NEW ONE
      // ==========================================
      else {
        // Catch the "NONE" signal if no opportunities were found
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({ 
            status: "WAITING", 
            message: "No active trade and no new signal found."
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        const currentPrice = await getPrice(signal.symbol);
        
        const newTrade = {
          active: true,
          symbol: signal.symbol,
          direction: signal.direction,
          entry_price: currentPrice,
          peak_pnl: 0,
          opened_at: Date.now()
        };

        if (isLiveMode) {
            // (Live open logic)
        }

        await updateGithubFile('active_trade.json', newTrade, tradeState.sha);

        return new Response(JSON.stringify({ 
          status: "OPENED", 
          symbol: signal.symbol, 
          direction: signal.direction,
          entry_price: currentPrice,
          mode: isLiveMode ? "LIVE" : "PAPER"
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  },
};
