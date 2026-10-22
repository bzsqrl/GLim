#pragma once
#include <FFGLSDK.h>
#include <chrono>
#include <memory>
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
	FFM_K_MOUSECLICK,// CPU-only: feeds ffm_Mouse.zw sign
	FFM_K_FFT        // FFGL buffer param filled with the host's audio spectrum
};

enum FFMSource
{
	FFM_SRC_HOST,
	FFM_SRC_TARGET,
	FFM_SRC_NONE,
	FFM_SRC_IMAGE,// embedded image (index into FFM_IMAGES)
	FFM_SRC_AUDIO // audio texture; index = rows (1 = FFT, 2 = FFT + wave, Shadertoy layout)
};

static const int FFM_FFT_SIZE = 512;

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

// time * sliders in the shader, kept as a running total (phase += scale * product
// of the params' values * frame time) so moving a slider changes the rate
// instead of jumping the animation.
struct FFMPhaseDef
{
	const char* uniform;
	float scale; // product of hidden (constant) params
	int count;   // live params multiplied in
	int defs[ 4 ];// indices into FFM_PARAMS
};

struct FFMSamplerDef
{
	const char* name;
	int source;
	int index;
	int filter;// -1 = the texture's own; else 0 nearest, 1 linear, 2 mipmap (per-channel Shadertoy sampler)
	int wrap;  // -1 = the texture's own; else 0 clamp, 1 repeat
};

struct FFMImageDef
{
	const char* name;
	const unsigned char* data;// encoded PNG/JPG/BMP/TGA bytes, or nullptr for generated noise
	unsigned int size;
	int noiseSize;           // used when data is nullptr
	int repeat;              // GL_REPEAT (1) or GL_CLAMP_TO_EDGE (0)
	int filter;              // 0 nearest, 1 linear, 2 mipmap
	int flip;                // load upright (Shadertoy vflip)
};

struct FFMTargetDef
{
	const char* name;
	int persistent;
	int isFloat;
	int mipmap;// some pass reads it with a mipmap filter: rebuild mipmaps after rendering
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

	void SetBeatInfo( float bpm, float barPhase ) override;

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

	std::vector< std::unique_ptr< ffglex::FFGLShader > > shaders;
	ffglex::FFGLScreenQuad quad;
	std::vector< Target > targets;
	GLuint blackTex = 0;
	std::vector< GLuint > imageTex;
	GLuint audioTex[ 3 ] = { 0, 0, 0 };// by row count
	GLuint samplerObj[ 3 ][ 2 ] = {};   // [filter][wrap], for FFMSamplerDef overrides
	int fftParam         = -1;          // FFGL index of the FFT buffer param
	void UpdateAudio();

	// Tempo from the host; until it sends any, 120 BPM from the real clock.
	bool hasBeatInfo   = false;
	float hostBpm      = 120.0f;
	float hostBarPhase = 0.0f;
	int hostBars       = 0;
	double realTime    = 0.0;

	double clockTime = 0.0;
	std::vector< double > phases;// FFM_PHASES running totals
	float lastDelta  = 0.0f;
	int frame        = 0;
	bool hasLastTick = false;
	std::chrono::steady_clock::time_point lastTick;
};
