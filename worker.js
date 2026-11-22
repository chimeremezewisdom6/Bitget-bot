// This endpoint is intentionally retired.
// Trade monitoring and exits now belong exclusively to scanner.py.
// Leaving the old endpoint active could apply conflicting 20-minute / percentage exits.
export default {
  async fetch() {
    return new Response(
      JSON.stringify({
        status: "DISABLED",
        message: "This legacy Worker is retired. The Bitget demo scanner manages its own trade state and exits."
      }),
      {
        status: 410,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
};
