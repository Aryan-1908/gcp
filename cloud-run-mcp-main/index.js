#!/usr/bin/env node

import express from 'express';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { registerTools, registerToolsRemote } from './tools.js';
import { SetLevelRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { registerPrompts } from './prompts.js';
import { checkGCP } from './lib/gcp-metadata.js';
import { GoogleAuth } from 'google-auth-library';
import { exec } from 'child_process';
import util from 'util';
import 'dotenv/config';

const execPromise = util.promisify(exec);

let gcpInfo = await checkGCP();
let gcpCredentialsAvailable = false;

function shouldStartHttp() {
  return true;
}

const envProjectId = process.env.GOOGLE_CLOUD_PROJECT || undefined;
const envRegion = process.env.GOOGLE_CLOUD_REGION;
const defaultServiceName = process.env.DEFAULT_SERVICE_NAME;
const skipIamCheck = process.env.SKIP_IAM_CHECK !== 'false';

async function getServer() {
  const server = new McpServer(
    {
      name: 'cloud-run',
      version: '1.0.0',
    },
    { capabilities: { logging: {} } }
  );

  server.server.setRequestHandler(SetLevelRequestSchema, (request) => {
    console.log(`Log Level: ${request.params.level}`);
    return {};
  });

  gcpInfo = await checkGCP();

  const effectiveProjectId =
    envProjectId || (gcpInfo && gcpInfo.project) || undefined;
  const effectiveRegion =
    envRegion || (gcpInfo && gcpInfo.region) || 'us-central1';

  const auth = new GoogleAuth({
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });

  try {
    const client = await auth.getClient();
    const project = effectiveProjectId || (await auth.getProjectId());
    gcpCredentialsAvailable = true;
    console.log(`✅ Authenticated with GCP project: ${project}`);
  } catch (err) {
    gcpCredentialsAvailable = false;
    console.warn('⚠️ Could not authenticate with GCP. Using local tools.');
  }

  if (!gcpCredentialsAvailable) {
    console.log('Using local tools.');
    await registerTools(server, {
      defaultProjectId: effectiveProjectId,
      defaultRegion: effectiveRegion,
      defaultServiceName,
      skipIamCheck,
      gcpCredentialsAvailable,
    });
  } else {
    console.log(
      `Using remote GCP tools for project: ${effectiveProjectId}, region: ${effectiveRegion}`
    );
    await registerToolsRemote(server, {
      defaultProjectId: effectiveProjectId,
      defaultRegion: effectiveRegion,
      defaultServiceName,
      skipIamCheck,
      gcpCredentialsAvailable,
    });
  }

  registerPrompts(server);
  return server;
}

if (shouldStartHttp()) {
  const app = express();
  app.use(express.json());

  // ✅ Existing MCP endpoint
  app.post('/mcp', async (req, res) => {
    console.log('/mcp Received:', req.body);
    const server = await getServer();
    try {
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
      });
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      res.on('close', () => {
        console.log('Request closed');
        transport.close();
        server.close();
      });
    } catch (error) {
      console.error('Error handling MCP request:', error);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: '2.0',
          error: { code: -32603, message: 'Internal server error' },
          id: null,
        });
      }
    }
  });

  // ✅ NEW: FinOps question handler
  // const functionMap = [
  //   { keywords: ['last month bill', 'previous bill'], func: 'get_last_month_bill' },
  //   { keywords: ['forecast', 'current month'], func: 'get_forecast' },
  //   { keywords: ['top services', 'high cost'], func: 'top_services' },
  //   { keywords: ['unused ip', 'free ip'], func: 'list_unused_ips' },
  //   { keywords: ['recommendations', 'cost saving'], func: 'get_recommendations' },
  //   { keywords: ['missing tags', 'untagged'], func: 'active_resources_missing_tags' }
  // ];

  // function detectFunction(question) {
  //   question = question.toLowerCase();
  //   for (const mapping of functionMap) {
  //     if (mapping.keywords.some(k => question.includes(k))) {
  //       return mapping.func;
  //     }
  //   }
  //   return null;
  // }

  app.post('/ask', async (req, res) => {
    const { input } = req.body;
    if (!input) return res.status(400).json({ error: 'Missing input' });

    console.log(`🔎 Executing Command: ${input}`);
    
    // Validate the command to avoid destructive operations
    if (!input.startsWith("gcloud")) {
        return res.status(400).json({ error: "Invalid command: Only gcloud commands allowed" });
    }

    try {
    //   const { stdout } = await execPromise(`python3 finops_tools.py ${funcName}`);
        const { stdout, stderr } = await execPromise(input);
        if (stderr) console.error(stderr);

        // Try to parse JSON if possible
        let parsed;
        try {
            parsed = JSON.parse(stdout);
        } catch (e) {
            parsed = stdout; // if not JSON, return raw text
        }

        res.json({ raw: stdout, parsed });
    } catch (err) {
        console.error('Error executing command:', err);
        res.status(500).json({ error: 'Execution failed' });
    }
  });

  // ✅ SSE Support
  const sseTransports = {};

  app.get('/sse', async (req, res) => {
    console.log('/sse Received');
    const server = await getServer();
    const transport = new SSEServerTransport('/messages', res);
    sseTransports[transport.sessionId] = transport;

    res.on('close', () => {
      delete sseTransports[transport.sessionId];
    });

    await server.connect(transport);
  });

  app.post('/messages', async (req, res) => {
    const sessionId = req.query.sessionId;
    const transport = sseTransports[sessionId];
    if (transport) {
      await transport.handlePostMessage(req, res, req.body);
    } else {
      res.status(400).send('No transport found for sessionId');
    }
  });

  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`🚀 Cloud Run MCP server listening at http://localhost:${PORT}`);
    console.log(`✅ FinOps endpoint available at http://localhost:${PORT}/ask`);
  });
}

process.on('SIGINT', async () => {
  console.log('Shutting down server...');
  process.exit(0);
});
