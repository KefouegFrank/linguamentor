import { prisma } from "../prisma/client";
import { AppError } from "../utils/errors";

export class UsageService {
  static async getOrCreateUsage(userId: string) {
    let usage = await prisma.userUsage.findUnique({ where: { userId } });
    if (!usage) {
      usage = await prisma.userUsage.create({
        data: { userId, tokensUsed: 0, dailyQuota: 20000, monthlyQuota: 300000 },
      });
    }
    return usage;
  }

  static async getUsage(userId: string) {
    return this.getOrCreateUsage(userId);
  }

  static async updateQuota(userId: string, quotas: { dailyQuota?: number; monthlyQuota?: number }) {
    const data: any = {};
    if (typeof quotas.dailyQuota === "number") data.dailyQuota = quotas.dailyQuota;
    if (typeof quotas.monthlyQuota === "number") data.monthlyQuota = quotas.monthlyQuota;
    if (!Object.keys(data).length) throw new AppError("No quota fields provided", 400);
    return prisma.userUsage.upsert({
      where: { userId },
      update: data,
      create: { userId, tokensUsed: 0, ...data },
    });
  }

  static async incrementTokens(userId: string, tokens: number) {
    if (!Number.isFinite(tokens) || tokens < 0) return this.getOrCreateUsage(userId);
    return prisma.userUsage.upsert({
      where: { userId },
      update: { tokensUsed: { increment: tokens } },
      create: { userId, tokensUsed: tokens },
    });
  }

  static async withinQuota(userId: string, tokensToConsume = 0) {
    const usage = await this.getOrCreateUsage(userId);
    const dailyOkay = usage.tokensUsed + tokensToConsume <= usage.dailyQuota;
    const monthlyOkay = usage.tokensUsed + tokensToConsume <= usage.monthlyQuota;
    return dailyOkay && monthlyOkay;
  }

  static async resetDaily() {
    await prisma.userUsage.updateMany({ data: { tokensUsed: 0, lastReset: new Date() } });
  }

  static async resetMonthly() {
    await prisma.userUsage.updateMany({ data: { tokensUsed: 0, lastReset: new Date() } });
  }
}

export const usageService = UsageService;
