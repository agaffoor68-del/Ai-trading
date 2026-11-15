"use client";

import { useState, useEffect } from "react";
import { MarketCalendar } from "@/app/core/market_calendar"; // This won't work, need to create a hook
import { useMarketCalendar } from "@/lib/market-calendar";

export function useMarketCalendar() {
  const [isMarketOpen, setIsMarketOpen] = useState(false);
  const [isTradingDay, setIsTradingDay] = useState(false);
  const [timeToClose, setTimeToClose] = useState(0);
  const [nextTradingDay, setNextTradingDay] = useState(new Date());

  useEffect(() => {
    const updateStatus = () => {
      const now = new Date();
      const istOffset = 5.5 * 60 * 60 * 1000; // IST is UTC+5:30
      const istNow = new Date(now.getTime() + istOffset);
      
      // Check if trading day (Mon-Fri, not holiday)
      const day = istNow.getUTCDay();
      const isWeekend = day === 0 || day === 6;
      
      // Simple holiday check (can be enhanced with actual holiday list)
      const isHoliday = false; // TODO: Implement holiday check
      
      const tradingDay = !isWeekend && !isHoliday;
      setIsTradingDay(tradingDay);
      
      // Market hours: 09:15 - 15:30 IST
      const hours = istNow.getUTCHours();
      const minutes = istNow.getUTCMinutes();
      const marketOpen = hours > 9 || (hours === 9 && minutes >= 15);
      const marketClose = hours < 15 || (hours === 15 && minutes <= 30);
      const open = tradingDay && marketOpen && marketClose;
      setIsMarketOpen(open);
      
      // Time to close
      if (open) {
        const closeTime = new Date(istNow);
        closeTime.setUTCHours(15, 30, 0, 0);
        const diffMs = closeTime.getTime() - istNow.getTime();
        setTimeToClose(Math.max(0, Math.floor(diffMs / 60000)));
      } else {
        setTimeToClose(0);
      }
      
      // Next trading day
      const nextDay = new Date(istNow);
      nextDay.setUTCDate(nextDay.getUTCDate() + 1);
      while (nextDay.getUTCDay() === 0 || nextDay.getUTCDay() === 6) {
        nextDay.setUTCDate(nextDay.getUTCDate() + 1);
      }
      setNextTradingDay(nextDay);
    };

    updateStatus();
    const interval = setInterval(updateStatus, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  return { isMarketOpen, isTradingDay, timeToClose, nextTradingDay };
}