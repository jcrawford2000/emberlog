// .eslintrc.cjs
module.exports = {
    root: true,
    env: { browser: true, es2020: true, node: true }, // Added 'node' for config files
    extends: [
        'eslint:recommended',
        'plugin:@typescript-eslint/recommended', // Base TS rules
        // 'plugin:@typescript-eslint/recommended-requiring-type-checking', // Stricter TS rules (optional)
        'plugin:react/recommended', // Base React rules
        'plugin:react/jsx-runtime', // For new JSX transform
        'plugin:react-hooks/recommended', // React Hooks rules
        'prettier', // Turns off ESLint rules that conflict with Prettier *must be last*
    ],
    ignorePatterns: ['dist', '.eslintrc.cjs', 'postcss.config.js', 'vite.config.ts'],
    parser: '@typescript-eslint/parser',
    parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        // project: ['./tsconfig.json', './tsconfig.node.json'], // Uncomment if using stricter TS rules
        // tsconfigRootDir: __dirname, // Uncomment if using stricter TS rules
    },
    settings: {
        react: {
            version: 'detect', // Auto-detect React version
        },
    },
    plugins: ['react-refresh'],
    rules: {
        'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
        'react/prop-types': 'off', // Disabled as we use TypeScript for props
        '@typescript-eslint/no-unused-vars': 'warn',
        // Add/override rules here
    },
};
