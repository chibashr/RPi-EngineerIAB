export default {
  testEnvironment: "jsdom",
  roots: ["<rootDir>/web/js/tests"],
  transform: {},
  collectCoverageFrom: [
    "web/js/**/*.{js,mjs}",
    "!web/js/tests/**",
    "!web/vendor/**",
  ],
  coverageDirectory: "coverage/js",
  coverageReporters: ["text", "lcov", "html"],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  testMatch: ["**/*.test.{js,mjs}"],
  moduleFileExtensions: ["js", "mjs", "json"],
};
