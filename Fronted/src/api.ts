import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 10000,
  withCredentials: true,
});

export default api;