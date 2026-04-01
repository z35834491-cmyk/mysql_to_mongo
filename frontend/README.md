# Shark Platform 前端

Vue 3 + Vite + Element Plus + Pinia。开发与构建说明见**仓库根目录** [README.md](../README.md)。

常用命令：

```bash
npm install
# Traffic 3D 地球使用 echarts-gl@2.x，仅与 ECharts 5 官方兼容；本项目锁定 echarts@5.5.x。
# 若升级 echarts 6，需等 echarts-gl 发支持版，否则控制台会报 glob "0" not found（globe 坐标系）。
npm run dev
npm run build
```
