#pragma once
#include <FFGLSDK.h>
#include <chrono>
#include <string>
#include <vector>

// ── Data-table types filled in by the generated ShaderData.h ────────────────

enum FFMKind
{
	FFM_K_FLOAT,
	FFM_K_INT,
	FFM_K_BOOL,
	FFM_K_EVENT,
	FFM_K_OPTION,
	FFM_K_COLOR,     // def = {h, s, v, a}; glslComponents 3 or 4
	FFM_K_POINT,     // def = {x, y}; min/max per axis
	FFM_K_SPEED,     // CPU-only: scales the clock
	FFM_K_MOUSE,     // CPU-only: feeds ffm_Mouse
	FFM_K_MOUSECLICK // CPU-only: feeds ffm_Mouse.zw sign
};

enum FFMSource
{
	FFM_SRC_HOST,
	FFM_SRC_TARGET,
	FFM_SRC_NONE
};

struct FFMParamDef
{
	const char* uniform;
	const char* label;
	int kind;
	float def[ 4 ];
	float min[ 2 ];
	float max[ 2 ];
	int glslComponents;
	int pixelSpace;
	const char* const* optLabels;
	const float* optValues;
	int numOptions;
};

struct FFMSamplerDef
{
	const char* name;
	int source;
	int index;
};

struct FFMTargetDef
{
	const char* name;
	int persistent;
	int isFloat;
};

struct FFMPassDef
{
	int program;
	int target;// -1 = host output
};

// ── Plugin ──────────────────────────────────────────────────────────────────

class FFMakerPlugin : public CFFGLPlugin
{
public:
	FFMakerPlugin();
	~FFMakerPlugin();

	FFResult InitGL( const FFGLViewportStruct* vp ) override;
	FFResult ProcessOpenGL( ProcessOpenGLStruct* pGL ) override;
	FFResult DeInitGL() override;

	FFResult SetFloatParameter( unsigned int index, float value ) override;
	float GetFloatParameter( unsigned int index ) override;
	char* GetParameterDisplay( unsigned int index ) override;

	// Value of a parameter by uniform name (used by pass size expressions).
	float P( const char* uniform ) const;

private:
	struct HostParam
	{
		int def; // index into FFM_PARAMS
		int sub; // component
	};
	struct Target
	{
		GLuint fbo[ 2 ] = { 0, 0 };
		GLuint tex[ 2 ] = { 0, 0 };
		int front       = 0;
		int w = 0, h = 0;
	};

	void AllocTarget( Target& t, int w, int h, bool isFloat );
	void FreeTarget( Target& t );
	float Value( int def, int sub ) const;
	void SendParams( GLuint program );

	std::vector< HostParam > hostParams;
	std::vector< float > values;
	std::vector< int > firstHostParam;// per def: index of its first FFGL param

	std::vector< ffglex::FFGLShader > shaders;
	ffglex::FFGLScreenQuad quad;
	std::vector< Target > targets;
	GLuint blackTex = 0;

	double clockTime = 0.0;
	float lastDelta  = 0.0f;
	int frame        = 0;
	bool hasLastTick = false;
	std::chrono::steady_clock::time_point lastTick;
};
