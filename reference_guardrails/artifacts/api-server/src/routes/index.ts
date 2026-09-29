import { Router, type IRouter } from "express";
import arbitrageRouter from "./arbitrage";
import healthRouter from "./health";

const router: IRouter = Router();

router.use(healthRouter);
router.use(arbitrageRouter);

export default router;
