import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, } from "@modelcontextprotocol/sdk/types.js";
// N8n configuration
let N8N_URL = process.env.N8N_URL || "https://n8nletsdo.online";
let N8N_SESSION_COOKIE = process.env.N8N_SESSION_COOKIE || "";
let N8N_API_KEY = process.env.N8N_API_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs";
let currentSession = null;
// Helper: Make authenticated request to N8n
async function n8nRequest(endpoint, options = {}) {
    const url = `${N8N_URL}${endpoint}`;
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };
    // PRIORITY 1: Try API key first (more reliable)
    if (N8N_API_KEY) {
        headers["X-N8N-API-KEY"] = N8N_API_KEY;
    }
    // PRIORITY 2: Try session cookie if no API key
    else if (currentSession && currentSession.expiresAt > Date.now()) {
        headers["Cookie"] = `n8n-auth=${currentSession.cookie}`;
    }
    else if (N8N_SESSION_COOKIE) {
        headers["Cookie"] = `n8n-auth=${N8N_SESSION_COOKIE}`;
    }
    const response = await fetch(url, {
        ...options,
        headers,
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`N8n API error (${response.status}): ${errorText}`);
    }
    return response.json();
}
// Helper: Find node by name in workflow
function findNodeByName(workflow, nodeName) {
    if (!workflow.nodes)
        return null;
    return workflow.nodes.find((n) => n.name === nodeName || n.id === nodeName);
}
// Helper: Find node by ID in workflow
function findNodeById(workflow, nodeId) {
    if (!workflow.nodes)
        return null;
    return workflow.nodes.find((n) => n.id === nodeId);
}
// Helper: Clean workflow for PUT request (remove read-only fields)
function cleanWorkflowForUpdate(workflow) {
    // Only keep fields that n8n API accepts for PUT
    return {
        name: workflow.name,
        nodes: workflow.nodes,
        connections: workflow.connections,
        settings: workflow.settings,
        staticData: workflow.staticData,
        pinData: workflow.pinData,
        active: workflow.active,
    };
}
// Create MCP Server
const server = new Server({
    name: "n8n-flexible-mcp",
    version: "1.0.0",
}, {
    capabilities: {
        tools: {},
    },
});
// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "n8n_set_api_key",
                description: "Set N8n API key for authenticated requests (recommended)",
                inputSchema: {
                    type: "object",
                    properties: {
                        apiKey: {
                            type: "string",
                            description: "N8n API key (JWT token)",
                        },
                        url: {
                            type: "string",
                            description: "N8n instance URL (optional, defaults to N8N_URL env var)",
                        },
                    },
                    required: ["apiKey"],
                },
            },
            {
                name: "n8n_set_session",
                description: "Set N8n session cookie for authenticated requests",
                inputSchema: {
                    type: "object",
                    properties: {
                        cookie: {
                            type: "string",
                            description: "N8n session cookie value (n8n-auth)",
                        },
                        url: {
                            type: "string",
                            description: "N8n instance URL (optional, defaults to N8N_URL env var)",
                        },
                    },
                    required: ["cookie"],
                },
            },
            {
                name: "n8n_get_workflow",
                description: "Get a workflow by ID",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                    },
                    required: ["workflowId"],
                },
            },
            {
                name: "n8n_list_workflows",
                description: "List all workflows",
                inputSchema: {
                    type: "object",
                    properties: {},
                },
            },
            {
                name: "n8n_update_node_code",
                description: "Update ONLY the code in a Code node (no full JSON needed!)",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        nodeName: {
                            type: "string",
                            description: "Name of the node to update",
                        },
                        code: {
                            type: "string",
                            description: "New JavaScript code for the node",
                        },
                    },
                    required: ["workflowId", "nodeName", "code"],
                },
            },
            {
                name: "n8n_update_node_parameters",
                description: "Update ONLY the parameters of a node (partial update)",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        nodeName: {
                            type: "string",
                            description: "Name of the node to update",
                        },
                        parameters: {
                            type: "object",
                            description: "New parameters (will be merged with existing)",
                        },
                    },
                    required: ["workflowId", "nodeName", "parameters"],
                },
            },
            {
                name: "n8n_get_node",
                description: "Get a specific node from a workflow",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        nodeName: {
                            type: "string",
                            description: "Name of the node",
                        },
                    },
                    required: ["workflowId", "nodeName"],
                },
            },
            {
                name: "n8n_add_node",
                description: "Add a new node to a workflow",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        node: {
                            type: "object",
                            description: "Node configuration (name, type, parameters, position)",
                        },
                        connectFrom: {
                            type: "string",
                            description: "Name of node to connect from (optional)",
                        },
                    },
                    required: ["workflowId", "node"],
                },
            },
            {
                name: "n8n_execute_workflow",
                description: "Execute a workflow",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        data: {
                            type: "object",
                            description: "Input data for the workflow (optional)",
                        },
                    },
                    required: ["workflowId"],
                },
            },
            {
                name: "n8n_get_executions",
                description: "Get execution history for a workflow",
                inputSchema: {
                    type: "object",
                    properties: {
                        workflowId: {
                            type: "string",
                            description: "Workflow ID",
                        },
                        limit: {
                            type: "number",
                            description: "Number of executions to return (default: 10)",
                        },
                    },
                    required: ["workflowId"],
                },
            },
        ],
    };
});
// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    try {
        switch (name) {
            case "n8n_set_api_key": {
                const { apiKey, url } = args;
                if (url)
                    N8N_URL = url;
                N8N_API_KEY = apiKey;
                return {
                    content: [{
                            type: "text",
                            text: `✅ API key set successfully for N8n at ${N8N_URL}`,
                        }],
                };
            }
            case "n8n_set_session": {
                const { cookie, url } = args;
                if (url)
                    N8N_URL = url;
                N8N_SESSION_COOKIE = cookie;
                currentSession = {
                    cookie,
                    expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
                };
                return {
                    content: [{
                            type: "text",
                            text: `Session set for N8n at ${N8N_URL}`,
                        }],
                };
            }
            case "n8n_get_workflow": {
                const { workflowId } = args;
                const workflow = await n8nRequest(`/api/v1/workflows/${workflowId}`);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify(workflow, null, 2),
                        }],
                };
            }
            case "n8n_list_workflows": {
                const result = await n8nRequest("/api/v1/workflows");
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify(result, null, 2),
                        }],
                };
            }
            case "n8n_get_node": {
                const { workflowId, nodeName } = args;
                const workflow = await n8nRequest(`/api/v1/workflows/${workflowId}`);
                const node = findNodeByName(workflow, nodeName);
                if (!node) {
                    throw new Error(`Node "${nodeName}" not found in workflow`);
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify(node, null, 2),
                        }],
                };
            }
            case "n8n_update_node_code": {
                const { workflowId, nodeName, code } = args;
                // Get current workflow
                const workflow = await n8nRequest(`/api/v1/workflows/${workflowId}`);
                // Find the node
                const node = findNodeByName(workflow, nodeName);
                if (!node) {
                    throw new Error(`Node "${nodeName}" not found in workflow`);
                }
                // Check if it's a Code node
                if (node.type !== "n8n-nodes-base.code") {
                    throw new Error(`Node "${nodeName}" is not a Code node (type: ${node.type})`);
                }
                // Update ONLY the code parameter
                node.parameters = node.parameters || {};
                node.parameters.jsCode = code;
                // Update the workflow (clean read-only fields first)
                const cleanedWorkflow = cleanWorkflowForUpdate(workflow);
                const updateResult = await n8nRequest(`/api/v1/workflows/${workflowId}`, {
                    method: "PUT",
                    body: JSON.stringify(cleanedWorkflow),
                });
                return {
                    content: [{
                            type: "text",
                            text: `Successfully updated code in node "${nodeName}".\n\nNode: ${nodeName}\nWorkflow: ${workflowId}\n\nUpdated code preview:\n${code.substring(0, 200)}...`,
                        }],
                };
            }
            case "n8n_update_node_parameters": {
                const { workflowId, nodeName, parameters } = args;
                // Get current workflow
                const workflow = await n8nRequest(`/api/v1/workflows/${workflowId}`);
                // Find the node
                const node = findNodeByName(workflow, nodeName);
                if (!node) {
                    throw new Error(`Node "${nodeName}" not found in workflow`);
                }
                // Merge parameters
                node.parameters = {
                    ...(node.parameters || {}),
                    ...parameters,
                };
                // Update the workflow (clean read-only fields first)
                const cleanedWorkflow = cleanWorkflowForUpdate(workflow);
                await n8nRequest(`/api/v1/workflows/${workflowId}`, {
                    method: "PUT",
                    body: JSON.stringify(cleanedWorkflow),
                });
                return {
                    content: [{
                            type: "text",
                            text: `Successfully updated parameters in node "${nodeName}".\n\nUpdated parameters:\n${JSON.stringify(parameters, null, 2)}`,
                        }],
                };
            }
            case "n8n_add_node": {
                const { workflowId, node, connectFrom } = args;
                // Get current workflow
                const workflow = await n8nRequest(`/api/v1/workflows/${workflowId}`);
                // Add node
                if (!workflow.nodes)
                    workflow.nodes = [];
                node.id = node.id || `node_${Date.now()}`;
                workflow.nodes.push(node);
                // Add connection if specified
                if (connectFrom && workflow.connections) {
                    const sourceNode = findNodeByName(workflow, connectFrom);
                    if (sourceNode) {
                        if (!workflow.connections[node.name]) {
                            workflow.connections[node.name] = { main: [[{}]] };
                        }
                    }
                }
                // Update the workflow (clean read-only fields first)
                const cleanedWorkflow = cleanWorkflowForUpdate(workflow);
                await n8nRequest(`/api/v1/workflows/${workflowId}`, {
                    method: "PUT",
                    body: JSON.stringify(cleanedWorkflow),
                });
                return {
                    content: [{
                            type: "text",
                            text: `Successfully added node "${node.name}" to workflow ${workflowId}.`,
                        }],
                };
            }
            case "n8n_execute_workflow": {
                const { workflowId, data } = args;
                const result = await n8nRequest(`/api/v1/workflows/${workflowId}/execute`, {
                    method: "POST",
                    body: JSON.stringify({ data: data || {} }),
                });
                return {
                    content: [{
                            type: "text",
                            text: `Workflow execution started:\n${JSON.stringify(result, null, 2)}`,
                        }],
                };
            }
            case "n8n_get_executions": {
                const { workflowId, limit = 10 } = args;
                const result = await n8nRequest(`/api/v1/executions?workflowId=${workflowId}&limit=${limit}`);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify(result, null, 2),
                        }],
                };
            }
            default:
                throw new Error(`Unknown tool: ${name}`);
        }
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: `Error: ${error instanceof Error ? error.message : String(error)}`,
                }],
            isError: true,
        };
    }
});
// Start server
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("N8n Flexible MCP Server running on stdio");
}
main().catch(console.error);

