class SymbolMapper:
    """Mapper to convert Fyers symbols to Kotak tokens."""

    def __init__(self, db_session):
        self.db_session = db_session
        self.fyers_to_kotak_cache = {}
        self._load_mapping()

    def _load_mapping(self):
        """Load symbol mapping from PostgreSQL instruments table."""
        try:
            from ...core.database import Instrument

            instruments = self.db_session.query(Instrument).all()

            for inst in instruments:
                self.fyers_to_kotak_cache[inst.symbol] = {
                    "token": inst.token,
                    "exchange": inst.exchange,
                    "name": inst.name,
                }

            logger.info(f"Loaded {len(instruments)} symbol mappings from DB")
        except Exception as e:
            logger.error(f"Error loading symbol mapping: {str(e)}")

    def get_kotak_token(self, fyers_symbol: str) -> dict:
        """
        Convert Fyers symbol to Kotak token lookup.

        Args:
            fyers_symbol: Fyers symbol (e.g., "NSE:NIFTY26OCT23100CE")

        Returns:
            dict with kotak token and metadata
        """
        try:
            symbol_parts = fyers_symbol.replace("NSE:", "").replace("NFO:", "")

            mapped = None
            for fyers_sym, data in self.fyers_to_kotak_cache.items():
                if fyers_sym in symbol_parts or symbol_parts in fyers_sym:
                    mapped = data
                    break

            if not mapped:
                mapped = self.fyers_to_kotak_cache.get(fyers_symbol, {"token": "", "exchange": "", "name": ""})

            return {
                "fyers_symbol": fyers_symbol,
                "kotak_token": mapped.get("token", ""),
                "exchange": mapped.get("exchange", ""),
                "name": mapped.get("name", ""),
                "found": mapped.get("token", "") != "",
            }
        except Exception as e:
            logger.error(f"Symbol mapper error for {fyers_symbol}: {str(e)}")
            return {
                "fyers_symbol": fyers_symbol,
                "kotak_token": "",
                "exchange": "",
                "name": "",
                "found": False,
                "error": str(e),
            }

    def update_mapping(self, fyers_symbol: str, kotak_token: str):
        """Update or add a symbol mapping."""
        try:
            from ...core.database import Instrument, SessionLocal

            db = SessionLocal()
            try:
                inst = db.query(Instrument).filter(Instrument.symbol == fyers_symbol).first()
                if inst:
                    inst.token = kotak_token
                    db.commit()
                    logger.info(f"Updated mapping: {fyers_symbol} -> {kotak_token}")
                else:
                    logger.warning(f"Symbol {fyers_symbol} not found in DB mapping")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating mapping: {str(e)}")